"""Pluggable cache for hut services.

The default backend is a file cache (pickled values, one file per key, atomic
writes).  Any object implementing :class:`CacheBackend` can replace it - most
notably Django's ``BaseCache`` (database, Redis, memcached, ...) which conforms
to the protocol as-is:

    from django.core.cache import cache
    from hut_services.core.cache import set_default_cache_backend

    set_default_cache_backend(cache)

Cache keys include the package version, function name and (non-ignored)
arguments, so results are not shared across upgrades.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import os
import pickle
import shutil
import tempfile
from collections.abc import Callable, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import time
from typing import Any, Protocol, TypeVar
from warnings import warn

__all__ = [
    "CacheBackend",
    "FileCacheBackend",
    "cached",
    "clear_cache",
    "clear_file_cache",
    "default_seconds",
    "file_cache",
    "forever_seconds",
    "get_default_cache_backend",
    "set_default_cache_backend",
]

cachedir = os.environ.get("HUT_SERVICE_CACHE_DIR", os.path.join(tempfile.gettempdir(), "py_file_cache"))
default_seconds = int(os.environ.get("HUT_SERVICE_EXPIRE_SECONDS", 3600 * 24 * 2))  # 2 days
forever_seconds = int(3600 * 24 * 365 * 10)  # 10 years

try:
    package_version = version("hut-services")
except PackageNotFoundError:  # source tree without installed metadata
    package_version = "0"

T = TypeVar("T")
_MISS = object()


class CacheBackend(Protocol):
    """Minimal KV cache protocol, matching Django's ``BaseCache`` API."""

    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any, timeout: int | None = None) -> None: ...
    def clear(self) -> None: ...


class FileCacheBackend:
    """Pickle-per-key file cache with atomic writes and per-entry TTL.

    A ``timeout`` of ``None`` falls back to ``default_timeout`` (Django
    semantics); entries are stored as ``(timeout, value)`` pickles and expire
    based on the file's mtime.
    """

    def __init__(self, directory: str | Path | None = None, default_timeout: int = default_seconds) -> None:
        self._root = Path(directory) if directory is not None else Path(cachedir) / "kv"
        self._default_timeout = default_timeout
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._root / digest[:2] / digest

    def get(self, key: str, default: Any = None) -> Any:
        path = self._path(key)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return default
        timeout, value = pickle.loads(data)  # noqa: S301 - trusted, own cache files
        if timeout is not None and time() - path.stat().st_mtime > timeout:
            path.unlink(missing_ok=True)
            return default
        return value

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        effective = self._default_timeout if timeout is None else timeout
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            pickle.dump((effective, value), fh)
        os.replace(tmp, path)  # atomic on POSIX and Windows

    def clear(self) -> None:
        if self._root.exists():
            shutil.rmtree(self._root)
        self._root.mkdir(parents=True, exist_ok=True)


_default_backend: CacheBackend = FileCacheBackend()


def get_default_cache_backend() -> CacheBackend:
    """Return the process-wide cache backend (a :class:`FileCacheBackend` unless replaced)."""
    return _default_backend


def set_default_cache_backend(backend: CacheBackend) -> None:
    """Replace the process-wide cache backend, e.g. a Django ``BaseCache``."""
    global _default_backend
    _default_backend = backend


def _cache_key(prefix: str, arguments: dict[str, Any]) -> str:
    payload = pickle.dumps(sorted(arguments.items(), key=lambda item: item[0]))
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"


def cached(
    func: Callable | None = None,
    *,
    ignore: Sequence[str] = (),
    expire_in_seconds: int | None = None,
    forever: bool = False,
    backend: CacheBackend | None = None,
) -> Any:
    """Cache a function's return values in the default (or given) backend.

    Keys are derived from the package version, the function's qualified name
    and its arguments; argument names in ``ignore`` (e.g. secrets or client
    objects) are excluded.  With ``forever`` the entry gets a 10-year timeout.
    """
    if forever:
        expire_in_seconds = forever_seconds
    elif expire_in_seconds is None:
        expire_in_seconds = default_seconds

    def decorator(fn: Callable) -> Callable:
        signature = inspect.signature(fn)
        key_prefix = f"{package_version}:{fn.__module__}:{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = backend if backend is not None else get_default_cache_backend()
            bound = signature.bind(*args, **kwargs)
            key = _cache_key(key_prefix, {k: v for k, v in bound.arguments.items() if k not in ignore})
            hit = cache.get(key, _MISS)
            if hit is not _MISS:
                return hit
            result = fn(*args, **kwargs)
            cache.set(key, result, expire_in_seconds)
            return result

        return wrapper

    if func is not None and callable(func):  # support bare @cached
        return decorator(func)
    return decorator


def file_cache(
    func: None | Callable = None,
    ignore: Sequence = (),
    expire_in_seconds: int | None = None,
    forever: bool = False,
) -> Any:
    """Deprecated alias for :func:`cached`."""
    warn("`file_cache` is deprecated, use `cached` instead.", DeprecationWarning, stacklevel=2)
    return cached(func, ignore=ignore, expire_in_seconds=expire_in_seconds, forever=forever)


def clear_cache() -> None:
    """Clear the default cache backend."""
    get_default_cache_backend().clear()


def clear_file_cache() -> None:
    """Deprecated alias for :func:`clear_cache`."""
    warn("`clear_file_cache` is deprecated, use `clear_cache` instead.", DeprecationWarning, stacklevel=2)
    clear_cache()
