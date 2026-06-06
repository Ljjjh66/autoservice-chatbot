import os
import numpy as np
from sentence_transformers import SentenceTransformer

KNOWLEDGE_DIR = "./data/knowledge"
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

_model = None
_chunks = []          # 存储所有文本块
_embeddings = None    # 存储所有向量 (numpy array)

def _get_model():
    global _model
    if _model is None:
        print("加载嵌入模型...")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = start + chunk_size - overlap
    return chunks

def build_knowledge_base():
    """加载文档、分块、生成向量，存入内存"""
    global _chunks, _embeddings

    print("=" * 60)
    print("开始构建知识库...")
    print("=" * 60)

    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)

    docs = {}
    for fname in os.listdir(KNOWLEDGE_DIR):
        if fname.endswith(".txt"):
            with open(os.path.join(KNOWLEDGE_DIR, fname), "r", encoding="utf-8") as f:
                docs[fname] = f.read()
            print(f"已加载文档: {fname}")

    if not docs:
        print("知识库为空！")
        return False

    _chunks = []
    for content in docs.values():
        _chunks.extend(chunk_text(content))

    print(f"共 {len(_chunks)} 个文本块")

    model = _get_model()
    print("生成向量嵌入...")
    _embeddings = model.encode(_chunks, show_progress_bar=True)

    print("知识库构建成功！（向量已存入内存）")
    return True

def search(query, top_k=2):
    """余弦相似度检索，返回最相关文本块"""
    if _embeddings is None or len(_chunks) == 0:
        print("错误: 知识库未构建，请先运行 build_knowledge_base()")
        return ""

    model = _get_model()
    query_vec = model.encode([query])[0]

    # 计算余弦相似度
    similarities = np.dot(_embeddings, query_vec) / (
        np.linalg.norm(_embeddings, axis=1) * np.linalg.norm(query_vec)
    )

    # 取 top_k
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = [_chunks[i] for i in top_indices]
    return "\n\n".join(results)

def _create_sample():
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    sample = os.path.join(KNOWLEDGE_DIR, "politicas.txt")
    if not os.path.exists(sample):
        with open(sample, "w", encoding="utf-8") as f:
            f.write("""Política de Envíos:
Puedes consultar el estado de tu pedido con el número que empieza por ESP. Estados: pendiente, enviado, en tránsito, entregado.

Modificación de Dirección:
Solo puedes cambiar la dirección si el pedido no ha sido enviado. Si está enviado o en tránsito no se puede modificar.

Devoluciones:
Tienes 30 días para devolver un producto. Debe estar en estado original.

Contacto:
Chat en vivo, correo soporte@tienda.es, teléfono +34 900 123 456.
""")
        print(f"已创建示例文档: {sample}")

if __name__ == "__main__":
    print("RAG 系统启动")
    _create_sample()
    if build_knowledge_base():
        print("\n" + "=" * 60)
        print("测试检索")
        print("=" * 60)
        q = "¿Cómo puedo cambiar la dirección de mi pedido?"
        print(f"问题: {q}")
        res = search(q, top_k=2)
        if res:
            print("检索结果:")
            print(res)
        else:
            print("无结果或检索失败。")
    else:
        print("知识库构建失败。")