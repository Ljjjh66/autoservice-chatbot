import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

KNOWLEDGE_DIR = "./data/knowledge"
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
CROSS_ENCODER_NAME = 'cross-encoder/ms-marco-MiniLM-L-6-v2'

# 检索参数
DEFAULT_TOP_K = 2
DEFAULT_SCORE_THRESHOLD = 0.3  # 相似度阈值，低于此分数的结果不返回
DEFAULT_DIVERSITY_THRESHOLD = 0.8  # 多样性阈值，超过此相似度的结果被去重

_model = None
_cross_encoder_model = None
_chunks = []          # 存储所有文本块
_chunk_sources = {}    # 存储每个块对应的来源文档
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
    global _chunks, _embeddings, _bm25_index, _tokenized_chunks, _chunk_sources

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
    _chunk_sources = {}
    chunk_id = 0
    
    for fname, content in docs.items():
        doc_chunks = chunk_text(content)
        for chunk in doc_chunks:
            _chunks.append(chunk)
            _chunk_sources[chunk_id] = fname
            chunk_id += 1

    print(f"共 {len(_chunks)} 个文本块，来自 {len(docs)} 个文档")

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

def _calculate_text_similarity(text1, text2):
    """计算两个文本的相似度（基于字符重叠）"""
    set1 = set(text1.lower())
    set2 = set(text2.lower())
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0

def _deduplicate_chunks(chunks_with_info, threshold=DEFAULT_DIVERSITY_THRESHOLD):
    """去重：基于文本相似度，去除重复的块"""
    if not chunks_with_info:
        return []
    
    unique_chunks = []
    for chunk_info in chunks_with_info:
        is_duplicate = False
        for existing in unique_chunks:
            sim = _calculate_text_similarity(chunk_info["chunk"], existing["chunk"])
            if sim > threshold:
                is_duplicate = True
                # 保留得分更高的，丢弃重复的
                if chunk_info["cross_score"] > existing["cross_score"]:
                    existing["is_duplicate"] = True
                    unique_chunks.remove(existing)
                    unique_chunks.append(chunk_info)
                break
        
        if not is_duplicate:
            chunk_info["is_duplicate"] = False
            unique_chunks.append(chunk_info)
    
    return unique_chunks

def search(query, top_k=DEFAULT_TOP_K, score_threshold=DEFAULT_SCORE_THRESHOLD):
    """
    混合检索 + Cross-Encoder 重排序 + 后处理
    
    改进点：
    1. 混合检索（向量 + BM25）
    2. Cross-Encoder 重排序
    3. 结果去重（基于文本相似度）
    4. 相似度阈值过滤
    5. 来源标注
    
    Args:
        query: 用户查询
        top_k: 返回结果数量
        score_threshold: 最低相似度阈值，低于此分数的结果不返回
    
    Returns:
        str: 格式化的检索结果（包含来源标注）
    """
    if _embeddings is None or len(_chunks) == 0 or _bm25_index is None:
        print("错误: 知识库未构建，请先运行 build_knowledge_base()")
        return ""

    print(f"\n开始混合检索 (top_k={top_k}, threshold={score_threshold}): {query}")
    print("-" * 60)

    # 步骤 a: 向量检索（扩大候选池）
    vector_candidate_indices = _vector_search(query, top_k * 3)
    print(f"向量检索候选: {len(vector_candidate_indices)} 个")

    # 步骤 b: BM25 检索（扩大候选池）
    bm25_candidate_indices = _bm25_search(query, top_k * 3)
    print(f"BM25 检索候选: {len(bm25_candidate_indices)} 个")

    # 步骤 c: 合并去重
    combined_indices = list(set(vector_candidate_indices) | set(bm25_candidate_indices))
    combined_chunks = [_chunks[i] for i in combined_indices]
    print(f"合并后候选: {len(combined_chunks)} 个")

    if len(combined_chunks) == 0:
        return ""

    # 步骤 d: Cross-Encoder 重排序
    cross_encoder = _get_cross_encoder()
    pairs = [(query, chunk) for chunk in combined_chunks]
    cross_scores = cross_encoder.predict(pairs)

    # 构建结果列表（包含索引、块、来源、得分）
    results = []
    for idx, chunk, cross_score in zip(combined_indices, combined_chunks, cross_scores):
        results.append({
            "index": idx,
            "chunk": chunk,
            "source": _chunk_sources.get(idx, "未知来源"),
            "cross_score": float(cross_score),
            "is_duplicate": False
        })

    # 步骤 e: 按得分排序
    results.sort(key=lambda x: x["cross_score"], reverse=True)

    print(f"Cross-Encoder 重排序后 top {min(5, len(results))} 个:")
    for i, r in enumerate(results[:5]):
        print(f"  {i+1}. 得分: {r['cross_score']:.4f} | 来源: {r['source']} | 预览: {r['chunk'][:50]}...")

    # 步骤 f: 去重（基于文本相似度）
    print(f"\n去重处理 (阈值={DEFAULT_DIVERSITY_THRESHOLD})...")
    unique_results = _deduplicate_chunks(results, threshold=DEFAULT_DIVERSITY_THRESHOLD)
    print(f"去重后剩余: {len(unique_results)} 个")

    # 步骤 g: 过滤低分结果
    filtered_results = [r for r in unique_results if r["cross_score"] >= score_threshold]
    print(f"阈值过滤后 (>= {score_threshold}): {len(filtered_results)} 个")

    # 步骤 h: 取 top_k
    final_results = filtered_results[:top_k]

    # 步骤 i: 格式化结果（包含来源标注）
    if not final_results:
        return ""

    formatted_results = []
    for i, r in enumerate(final_results):
        source_note = f"[来源: {r['source']}]"
        chunk_with_source = f"{source_note}\n{r['chunk']}"
        formatted_results.append(chunk_with_source)

    print(f"\n最终返回 {len(final_results)} 个结果:")
    for i, r in enumerate(final_results):
        print(f"  {i+1}. [{r['source']}] 得分: {r['cross_score']:.4f}")

    return "\n\n---\n\n".join(formatted_results)

def search_detailed(query, top_k=DEFAULT_TOP_K):
    """
    详细检索版本，返回完整的结果信息（用于调试和分析）
    
    Returns:
        dict: 包含所有检索结果的详细信息
    """
    if _embeddings is None or len(_chunks) == 0 or _bm25_index is None:
        return {"error": "知识库未构建"}
    
    # 执行混合检索
    vector_candidates = _vector_search(query, top_k * 3)
    bm25_candidates = _bm25_search(query, top_k * 3)
    combined = list(set(vector_candidates) | set(bm25_candidates))
    
    cross_encoder = _get_cross_encoder()
    chunks = [_chunks[i] for i in combined]
    scores = cross_encoder.predict([(query, c) for c in chunks])
    
    results = []
    for idx, chunk, score in zip(combined, chunks, scores):
        results.append({
            "index": idx,
            "chunk": chunk,
            "source": _chunk_sources.get(idx, "未知"),
            "score": float(score)
        })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "query": query,
        "total_chunks": len(_chunks),
        "candidates": len(combined),
        "results": results[:top_k]
    }

def _create_sample():
    """创建示例文档（如果知识库为空）"""
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
    print("RAG 系统启动（混合检索 + Cross-Encoder 重排序 + 后处理）")
    print("改进点：结果去重、来源标注、相似度阈值过滤\n")
    
    _create_sample()
    if build_knowledge_base():
        print("\n" + "=" * 60)
        print("测试检索（西班牙语）")
        print("=" * 60)
        
        test_queries = [
            "¿Cómo puedo cambiar la dirección de mi pedido?",
            "¿Cuál es la política de devoluciones?",
            "¿Cuánto cuesta el envío a Estados Unidos?",
        ]
        
        for q in test_queries:
            print(f"\n问题: {q}")
            res = search(q, top_k=2)
            if res:
                print("\n最终检索结果:")
                print("-" * 60)
                print(res)
            else:
                print("无结果或检索失败。")
            print("\n" + "=" * 60)
    else:
        print("知识库构建失败。")
