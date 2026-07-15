"""
Security guardrails for the ARECCA LangGraph pipeline.
Reference: LLM-RAG-PIPELINE / src/graph/guardrails.py

Optimizations:
  - Single compiled alternation regex (O(n) → O(1) per check)
  - LRU result cache keyed by content_hash
  - Early termination on first blocked finding
  - First-chunk-only content scanning (4KB)
"""
import re
from functools import lru_cache
from typing import Optional

# ── Injection patterns: single alternation regex ──────────────────────
_INJECTION_RE = re.compile(
    r"(?i)"
    r"(?:"
    r"ignore\s+(?:above|all|previous)\s+(?:instructions|prompt|commands)"
    r"|system\s+prompt"
    r"|role\s*[:=]\s*(?:system|assistant)"
    r"|you\s+(?:are\s+)?(?:now|must\s+now)\s+(?:a|an)\s+"
    r"|```.*system"
    r"|<\|im_start\|>|<\|im_end\|>"
    r"|\{\{.*\}\}"
    r")"
)

# ── Malicious content patterns: single byte alternation ──────────────
_MALICIOUS_CONTENT_RE = re.compile(
    rb"(?i)"
    rb"(?:"
    rb"<script[^>]*>"
    rb"|<\?php"
    rb"|eval\s*\([^)]*\)"
    rb"|base64\s*,\s*[A-Za-z0-9+/]{100,}={0,2}"
    rb")"
)

# ── Blocked extensions (O(1) set lookup) ─────────────────────────────
_BLOCKED_EXTENSIONS = frozenset({
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js", ".vba", ".scr", ".com"
})

# ── Max file size from config (lazy loaded) ──────────────────────────
_MAX_FILE_SIZE_MB: int | None = None


def _get_max_size() -> int:
    global _MAX_FILE_SIZE_MB
    if _MAX_FILE_SIZE_MB is None:
        from src.config import cfg
        _MAX_FILE_SIZE_MB = cfg.get("storage", {}).get("max_file_size_mb", 50)
    return _MAX_FILE_SIZE_MB


# ── Input security with LRU result cache ─────────────────────────────
@lru_cache(maxsize=256)
def _cached_input_check(
    filename: str,
    content_head: bytes,
    content_hash: str,
    file_size_bytes: int,
    max_size_mb: int,
) -> dict:
    issues: list[str] = []
    risk: str = "safe"

    low = filename.lower()
    if any(low.endswith(ext) for ext in _BLOCKED_EXTENSIONS):
        ext = filename.rsplit(".", 1)[-1]
        return {
            "decision": "blocked",
            "issues": [f"Blocked file extension: .{ext}"],
            "content_hash": content_hash,
            "extension": ext,
            "size_bytes": file_size_bytes,
        }

    if file_size_bytes > max_size_mb * 1024 * 1024:
        return {
            "decision": "blocked",
            "issues": [f"File exceeds {max_size_mb}MB limit ({file_size_bytes / 1024 / 1024:.1f}MB)"],
            "content_hash": content_hash,
            "extension": filename.rsplit(".", 1)[-1] if "." in filename else "",
            "size_bytes": file_size_bytes,
        }

    if content_head and _MALICIOUS_CONTENT_RE.search(content_head):
        return {
            "decision": "blocked",
            "issues": ["Potentially malicious content pattern detected in file header"],
            "content_hash": content_hash,
            "extension": filename.rsplit(".", 1)[-1] if "." in filename else "",
            "size_bytes": file_size_bytes,
        }

    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    return {
        "decision": risk,
        "issues": issues,
        "content_hash": content_hash,
        "extension": ext,
        "size_bytes": file_size_bytes,
    }


def check_input_security(
    filename: str,
    content: bytes,
    content_hash: str,
    file_size_bytes: int,
    max_file_size_mb: int | None = None,
) -> dict:
    mbs = max_file_size_mb or _get_max_size()
    head = content[:4096] if content else b""
    return _cached_input_check(filename, head, content_hash, file_size_bytes, mbs)


def invalidate_cache() -> None:
    _cached_input_check.cache_clear()


# ── Text injection (single alternation regex, no loop) ───────────────
def check_text_injection(text: str) -> Optional[dict]:
    m = _INJECTION_RE.search(text)
    if m:
        return {
            "decision": "suspicious",
            "reason": f"Injection pattern matched: {m.group()[:80]}",
            "pattern": _INJECTION_RE.pattern[:60],
        }
    return None


# ── Output security (single-pass, early exit) ────────────────────────
_REQUIRED_FIELDS = frozenset({"lease_start_date", "base_rent_monthly", "lease_term_months"})
_RISK_WEIGHTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def check_output_security(
    extraction: Optional[dict],
    compliance_report: Optional[dict],
) -> dict:
    issues: list[str] = []
    risk: str = "safe"

    if not extraction:
        return {
            "decision": "warning",
            "issues": ["No extraction data produced"],
        }

    confidence = extraction.get("confidence_score", 0)
    if confidence < 0.3:
        issues.append(f"Low extraction confidence: {confidence:.2f}")
        risk = "warning"

    lease_terms = extraction.get("lease_terms", {}) or {}
    present = {f for f in _REQUIRED_FIELDS if lease_terms.get(f) is not None}
    if len(present) <= 1:
        missing = sorted(_REQUIRED_FIELDS - present)
        issues.append(f"Missing {len(missing)} critical fields: {missing}")
        risk = "warning"

    if compliance_report:
        rl = compliance_report.get("overall_risk_level", "low")
        if rl in ("high", "critical"):
            issues.append(f"Compliance risk level: {rl}")
            risk = "flagged"

    return {"decision": risk, "issues": issues}
