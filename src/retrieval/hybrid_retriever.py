from llama_index.core import Settings
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core import VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor
from src.config import cfg
from src.vectordb.qdrant_store import get_qdrant_vector_store


_retrieval_cfg = cfg.get("retrieval", {})
TOP_K = _retrieval_cfg.get("top_k", 5)
CUTOFF = _retrieval_cfg.get("similarity_cutoff", 0.7)
ALPHA = _retrieval_cfg.get("alpha", 0.3)


def get_hybrid_retriever():
    vector_store = get_qdrant_vector_store()
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=Settings.embed_model,
    )
    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=TOP_K,
        vector_store_query_mode="hybrid",
        alpha=ALPHA,
        sparse_top_k=TOP_K * 2,
    )
    return retriever


def get_query_engine():
    retriever = get_hybrid_retriever()
    return RetrieverQueryEngine(
        retriever=retriever,
        node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=CUTOFF)],
    )
