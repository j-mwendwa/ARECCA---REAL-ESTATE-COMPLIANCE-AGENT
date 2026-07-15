"""
LangSmith opt-in tracing setup.
Reference: LLM-RAG-PIPELINE / src/core/tracing.py
"""
import os
import structlog

from src.config import settings

logger = structlog.get_logger()


def setup_langsmith() -> None:
    if settings.langsmith_api_key and settings.langsmith_tracing:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "arecca")
        logger.info("langsmith_tracing_enabled", project="arecca")
    else:
        os.environ.setdefault("LANGSMITH_TRACING", "false")
        logger.debug("langsmith_tracing_disabled")
