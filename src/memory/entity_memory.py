"""
Per-document durable key-value fact storage.
Reference: LLM-RAG-PIPELINE / src/memory/entity_memory.py
"""
import json
import os
from pathlib import Path
from typing import Optional


_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "memory"
_ENCRYPTION_KEY = os.getenv("MEMORY_ENCRYPTION_KEY", "")
_ENCRYPTED_PREFIX = "ENCRYPTED_V1:"

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None and _ENCRYPTION_KEY:
        try:
            from cryptography.fernet import Fernet
            key = _ENCRYPTION_KEY.encode() if _ENCRYPTION_KEY.endswith("=") else Fernet.generate_key()
            _fernet = Fernet(key)
        except Exception:
            _fernet = None
    return _fernet


def _memory_path(document_id: str) -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / f"{document_id}.json"


class EntityMemory:
    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        self._path = _memory_path(document_id)
        self._facts: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = self._path.read_text(encoding="utf-8")
        if raw.startswith(_ENCRYPTED_PREFIX):
            f = _get_fernet()
            if f:
                raw = f.decrypt(raw[len(_ENCRYPTED_PREFIX):].encode()).decode()
            else:
                raise RuntimeError("Encrypted memory but no encryption key available")
        self._facts = json.loads(raw)

    def _save(self) -> None:
        raw = json.dumps(self._facts, indent=2)
        f = _get_fernet()
        if f:
            encrypted = _ENCRYPTED_PREFIX + f.encrypt(raw.encode()).decode()
            self._path.write_text(encrypted, encoding="utf-8")
        else:
            self._path.write_text(raw, encoding="utf-8")

    def remember(self, key: str, value: str) -> None:
        self._facts[key] = value
        self._save()

    def update(self, facts: dict[str, str]) -> None:
        self._facts.update(facts)
        self._save()

    def all(self) -> dict[str, str]:
        return dict(self._facts)

    def get(self, key: str) -> Optional[str]:
        return self._facts.get(key)

    def clear(self) -> None:
        self._facts.clear()
        if self._path.exists():
            self._path.unlink()

    @property
    def summary(self) -> str:
        if not self._facts:
            return ""
        return "\n".join(f"- {k}: {v}" for k, v in self._facts.items())
