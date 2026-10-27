"""Versioned UTF-8 snapshots and atomic text saves within one server process."""
import hashlib
import os
import stat
import tempfile
import threading
from pathlib import Path

_lock = threading.Lock()


class FileConflictError(Exception):
    pass


def _version(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: str) -> dict:
    with _lock:
        data = Path(path).read_bytes()
        return {"content": data.decode("utf-8"), "version": _version(data)}


def save_text(path: str, content: str, expected_version: str | None = None) -> dict:
    # Resolve symlinks so atomic replacement preserves the link itself.
    target = Path(path).resolve()
    data = content.encode("utf-8")
    with _lock:
        current = target.read_bytes() if target.exists() else None
        if expected_version is not None and (current is None or _version(current) != expected_version):
            raise FileConflictError("File changed or was deleted. Local edits have been preserved.")
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = stat.S_IMODE(target.stat().st_mode) if current is not None else None
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if mode is not None:
                os.chmod(temporary, mode)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"success": True, "version": _version(data)}
