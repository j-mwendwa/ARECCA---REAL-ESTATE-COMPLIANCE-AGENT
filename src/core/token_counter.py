"""
Token counter using tiktoken cl100k_base.
Reference: LLM-RAG-PIPELINE / src/core/token_counter.py
"""
import tiktoken

_ENCODING = "cl100k_base"
_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding(_ENCODING)
    return _encoder


def count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    encoder = _get_encoder()
    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoder.decode(tokens[:max_tokens])
