from pathlib import Path

from src.ingestion.storage import save_file, copy_file, delete_file
from src.core.exceptions import StorageError


def test_save_and_read(tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config.settings, "storage_path", str(tmp_path))
    data = b"test pdf content"
    path = save_file(data, "leases/2024/01/test.pdf")
    saved = Path(path)
    assert saved.exists()
    assert saved.read_bytes() == data


def test_copy_file(tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config.settings, "storage_path", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"original content")
    dest = copy_file(str(source), "copies/copied.pdf")
    copied = Path(dest)
    assert copied.exists()
    assert copied.read_bytes() == b"original content"


def test_delete_file(tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config.settings, "storage_path", str(tmp_path))
    path = save_file(b"to delete", "delete_me.pdf")
    assert Path(path).exists()
    delete_file("delete_me.pdf")
    assert not Path(path).exists()


def test_delete_nonexistent(tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config.settings, "storage_path", str(tmp_path))
    delete_file("not_there.pdf")


def test_copy_nonexistent_source(tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config.settings, "storage_path", str(tmp_path))
    try:
        copy_file("/nonexistent/file.pdf")
        assert False, "Expected StorageError"
    except StorageError:
        pass
