"""
Centralized LlamaIndex embedding and global settings configuration.
Reference: LLM-RAG-PIPELINE / src/core/llamaindex_setup.py
"""
import structlog
from llama_index.core import Settings

from src.config import cfg

logger = structlog.get_logger()

_EMBED_MODEL = cfg.get("embedding", {}).get("model", "nlpaueb/legal-bert-base-uncased")
_EMBED_DIM = cfg.get("embedding", {}).get("dimensions", 768)
_EMBED_PROVIDER = cfg.get("embedding", {}).get("provider", "huggingface")

_initialized = False


def setup_llamaindex() -> None:
    global _initialized
    if _initialized:
        return

    if not Settings.embed_model:
        if _EMBED_PROVIDER == "huggingface":
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            Settings.embed_model = HuggingFaceEmbedding(
                model_name=_EMBED_MODEL,
                embed_batch_size=32,
            )
            logger.info("embed_model_loaded", model=_EMBED_MODEL, dimensions=_EMBED_DIM)
        else:
            logger.warning("unknown_embed_provider", provider=_EMBED_PROVIDER)

    _initialized = True
