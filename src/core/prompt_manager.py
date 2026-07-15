"""
Versioned prompt loader.
Reference: LLM-RAG-PIPELINE / src/core/prompt_manager.py
"""
from pathlib import Path
from typing import Optional

from src.config import cfg

_PROMPTS_ROOT = Path(__file__).parent.parent.parent / "prompts"
_HOT_RELOAD = cfg.get("prompts", {}).get("hot_reload", False)
_VERSION = cfg.get("prompts", {}).get("version", "v1")

_cache: dict[str, str] = {}


def load_prompt(name: str, version: Optional[str] = None) -> str:
    ver = version or _VERSION
    key = f"{name}_{ver}"

    if not _HOT_RELOAD and key in _cache:
        return _cache[key]

    candidates = [
        _PROMPTS_ROOT / name / f"{name}_{ver}.md",
        _PROMPTS_ROOT / f"{name}" / f"{name}_{ver}.md",
        _PROMPTS_ROOT / name / f"{name}.md",
        _PROMPTS_ROOT / f"{name}.md",
    ]

    for candidate in [p for p in candidates if p.exists()]:
        text = candidate.read_text(encoding="utf-8")
        _cache[key] = text
        return text

    for subdir in sorted(_PROMPTS_ROOT.rglob(f"*{name}*{ver}.md")):
        text = subdir.read_text(encoding="utf-8")
        _cache[key] = text
        return text

    for subdir in sorted(_PROMPTS_ROOT.rglob(f"*{name}*.md")):
        text = subdir.read_text(encoding="utf-8")
        _cache[key] = text
        return text

    msg = f"Prompt '{name}' (version {ver}) not found in {_PROMPTS_ROOT}"
    raise FileNotFoundError(msg)


def list_prompts() -> list[Path]:
    return sorted(_PROMPTS_ROOT.rglob("*.md"))


def clear_cache() -> None:
    _cache.clear()
