from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from src.config import settings, cfg

COLLECTION_NAME = "lease_sections"
VECTOR_SIZE = cfg.get("embedding", {}).get("dimensions", 768)
SPARSE_MODEL = "Qdrant/bm25"


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        prefer_grpc=True,
    )


def ensure_collection(client: QdrantClient | None = None) -> None:
    close = False
    if client is None:
        client = get_qdrant_client()
        close = True
    try:
        existing = client.collection_exists(COLLECTION_NAME)
        if not existing:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )
    except UnexpectedResponse:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                )
            },
        )
    finally:
        if close:
            client.close()


def get_qdrant_vector_store():
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    return QdrantVectorStore(
        collection_name=COLLECTION_NAME,
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        enable_hybrid=True,
        fastembed_sparse_model=SPARSE_MODEL,
        batch_size=100,
    )
