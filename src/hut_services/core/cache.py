import os
import tempfile
from typing import Any, Sequence

from joblib import Memory, expires_after  # type: ignore[import-untyped]

__all__ = ["file_cache", "clear_file_cache"]


cachedir = os.environ.get("HUT_SERVICE_CACHE_DIR", os.path.join(tempfile.gettempdir(), "py_file_cache"))
default_seconds = int(os.environ.get("HUT_SERVICE_EXPIRE_SECONDS", 3600 * 24 * 2))  # 2 days
_memory = Memory(cachedir, verbose=0, compress=True)


def file_cache(ignore: Sequence = [], expire_in_seconds: int = default_seconds) -> Any:
    return _memory.cache(ignore=ignore, cache_validation_callback=expires_after(seconds=expire_in_seconds))


clear_file_cache = _memory.clear
"""Cleares cache."""
