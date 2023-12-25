import os
import tempfile
from typing import Any, Sequence

from joblib import Memory, expires_after  # type: ignore[import-untyped]

__all__ = ["file_cache", "clear_file_cache"]


cachedir = os.environ.get("HUT_SERVICE_CACHE_DIR", os.path.join(tempfile.gettempdir(), "py_file_cache"))
default_days = int(os.environ.get("HUT_SERVICE_EXPIRE_DAYS", 2))
_memory = Memory(cachedir, verbose=0, compress=True)


def file_cache(ignore: Sequence = [], days: int = default_days) -> Any:
    return _memory.cache(ignore=ignore, cache_validation_callback=expires_after(days=days))


clear_file_cache = _memory.clear
"""Cleares cache."""
