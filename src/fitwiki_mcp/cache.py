"""Private, account-scoped, atomic JSON cache with parser-versioned keys."""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from .errors import WikiError

CACHE_VERSION = 2


def private_dir(path: Path) -> Path:
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise WikiError("STORAGE_ERROR", "Private storage must not be a symbolic link.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise WikiError(
            "STORAGE_ERROR",
            "Storage directory is accessible to other users; choose a private (0700) directory.",
        )
    return path


def atomic_json(path: Path, value: dict) -> None:
    private_dir(path.parent)
    if path.is_symlink():
        raise WikiError("STORAGE_ERROR", "Refusing symbolic-link cache entry.")
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Cache:
    def __init__(self, root: Path):
        self.root = private_dir(root)

    def path(self, key: str) -> Path:
        digest = hashlib.sha256(f"{CACHE_VERSION}:{key}".encode()).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, key: str) -> dict | None:
        path = self.path(key)
        if path.is_symlink():
            raise WikiError("STORAGE_ERROR", "Refusing symbolic-link cache entry.")
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            return (
                result
                if isinstance(result, dict) and "stored_at" in result and "value" in result
                else None
            )
        except (FileNotFoundError, ValueError, OSError):
            return None

    def put(self, key: str, value: dict) -> dict:
        entry = {"stored_at": time.time(), "value": value}
        atomic_json(self.path(key), entry)
        return entry
