import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

KNOWLEDGE_DIR = "./data/knowledge"
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
CROSS_ENCODER_NAME = 'cross-encoder/ms-marco-MiniLM-L-6-v2'

_model = None
_cross_encoder_model = None
_chunks = []          # 存储所有文本块
_embeddings = None    # 存储所有向量 (numpy array)
_bm25_index = None    # BM25 索引
_tokenized_chunks = []  # 分词后的文本块

def _get_model():
    global _model
    if _model is None:
        print("加载嵌入模型...")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def _get_cross_encoder():
    global _cross_encoder_model
    if _cross_encoder_model is None:
        print("加载 Cross-Encoder 重排序模型...")
        _cross_encoder_model = CrossEncoder(CROSS_ENCODER_NAME)
    return _cross_encoder_model

def _simple_tokenize(text):
    """简单的分词函数（支持西班牙语）"""
    # 转小写，移除特殊字符，按空格分词
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.split()

def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = start + chunk_size - overlap
    return chunks

def build_knowledge_base():
    """加载文档、分块、生成向量，存入内存（包括 BM25 索引）"""
    global _chunks, _embeddings, _bm25_index, _tokenized_chunks

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

    # 构建向量索引
    model = _get_model()
    print("生成向量嵌入...")
    _embeddings = model.encode(_chunks, show_progress_bar=True)

    # 构建 BM25 索引
    print("构建 BM25 索引...")
    _tokenized_chunks = [_simple_tokenize(chunk) for chunk in _chunks]
    _bm25_index = BM25Okapi(_tokenized_chunks)

    print("知识库构建成功！（向量和 BM25 索引已存入内存）")
    return True

def _vector_search(query, top_k):
    """纯向量检索"""
    model = _get_model()
    query_vec = model.encode([query])[0]

    # 计算余弦相似度
    similarities = np.dot(_embeddings, query_vec) / (
        np.linalg.norm(_embeddings, axis=1) * np.linalg.norm(query_vec)
    )

    # 取 top_k
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return top_indices

def _bm25_search(query, top_k):
    """纯 BM25 检索"""
    if _bm25_index is None:
        return []

    tokenized_query = _simple_tokenize(query)
    scores = _bm25_index.get_scores(tokenized_query)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return top_indices

def search(query, top_k=2):
    """混合检索（向量 + BM25）+ Cross-Encoder 重排序"""
    if _embeddings is None or len(_chunks) == 0 or _bm25_index is None:
        print("错误: 知识库未构建，请先运行 build_knowledge_base()")
        return ""

    print(f"开始混合检索 (top_k={top_k}): {query}")

    # 步骤 a: 向量检索（扩大候选池）
    vector_candidate_indices = _vector_search(query, top_k * 2)
    print(f"向量检索候选: {len(vector_candidate_indices)} 个")

    # 步骤 b: BM25 检索（扩大候选池）
    bm25_candidate_indices = _bm25_search(query, top_k * 2)
    print(f"BM25 检索候选: {len(bm25_candidate_indices)} 个")

    # 步骤 c: 合并去重
    combined_indices = list(set(vector_candidate_indices) | set(bm25_candidate_indices))
    combined_chunks = [_chunks[i] for i in combined_indices]
    print(f"合并去重后: {len(combined_chunks)} 个候选")

    if len(combined_chunks) == 0:
        return ""

    # 步骤 d: Cross-Encoder 重排序
    cross_encoder = _get_cross_encoder()
    pairs = [(query, chunk) for chunk in combined_chunks]
    scores = cross_encoder.predict(pairs)

    # 组合索引和分数
    scored_results = list(zip(combined_indices, combined_chunks, scores))
    scored_results.sort(key=lambda x: x[2], reverse=True)

    # 步骤 e: 返回分值最高的 top_k 个
    top_results = scored_results[:top_k]
    result_chunks = [chunk for (idx, chunk, score) in top_results]

    print(f"重排序完成，返回 top {len(result_chunks)} 个结果")
    for i, (idx, chunk, score) in enumerate(top_results[:3]):
        print(f"  {i+1}. 得分: {score:.4f}, 内容预览: {chunk[:60]}...")

    return "\n\n".join(result_chunks)

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
    print("RAG 系统启动（混合检索 + Cross-Encoder 重排序）")
    _create_sample()
    if build_knowledge_base():
        print("\n" + "=" * 60)
        print("测试检索（西班牙语）")
        print("=" * 60)
        q = "¿Cómo puedo cambiar la dirección de mi pedido?"
        print(f"问题: {q}")
        res = search(q, top_k=2)
        if res:
            print("\n最终检索结果:")
            print("-" * 60)
            print(res)
        else:
            print("无结果或检索失败。")
    else:
        print("知识库构建失败。")
