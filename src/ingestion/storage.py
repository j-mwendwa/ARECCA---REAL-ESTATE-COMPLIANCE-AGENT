from pathlib import Path
import shutil

from src.config import settings
from src.core.exceptions import StorageError


def _storage_dir() -> Path:
    return Path(settings.storage_path)


def _ensure_dir() -> None:
    _storage_dir().mkdir(parents=True, exist_ok=True)


def save_file(data: bytes, destination: str) -> str:
    _ensure_dir()
    dest = _storage_dir() / destination
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(data)
        return str(dest)
    except Exception as e:
        raise StorageError(f"Failed to write file: {e}") from e


def copy_file(source: str | Path, destination: str | None = None) -> str:
    _ensure_dir()
    src = Path(source)
    if not src.exists():
        raise StorageError(f"File not found: {src}")
    dest = _storage_dir() / (destination or src.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dest)
        return str(dest)
    except Exception as e:
        raise StorageError(f"Failed to copy file: {e}") from e


def delete_file(name: str) -> None:
    dest = _storage_dir() / name
    try:
        dest.unlink(missing_ok=True)
    except Exception as e:
        raise StorageError(f"Failed to delete file: {e}") from e
