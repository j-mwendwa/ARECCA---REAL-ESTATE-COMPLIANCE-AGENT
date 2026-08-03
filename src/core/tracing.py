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


def traceable(
    func=None,
    *,
    name: str | None = None,
    run_type: str = "chain",
    **kwargs,
):
    """
    Decorator that wraps a function with a LangSmith trace span.
    Falls back to a transparent no-op when LangSmith is unconfigured.

    Usage::

        @traceable(name="node.extract")
        async def extract_node(state): ...

        @traceable
        def my_func(): ...
    """

    def decorator(fn):
        try:
            from langsmith import traceable as _ls_traceable  # type: ignore

            span_name = name or fn.__qualname__
            return _ls_traceable(name=span_name, run_type=run_type, **kwargs)(fn)
        except ImportError:
            return fn

    if func is not None:
        return decorator(func)
    return decorator
