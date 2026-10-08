"""Tests for the pluggable cache: protocol, file backend, decorator."""

import pytest
from pydantic import BaseModel

from hut_services import clear_cache
from hut_services.core import cache as cache_mod
from hut_services.core.cache import (
    FileCacheBackend,
    cached,
    get_default_cache_backend,
    set_default_cache_backend,
)


class DictCache:
    """Minimal CacheBackend implementation (Django-BaseCache-shaped)."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value, timeout=None):
        self.store[key] = value

    def clear(self) -> None:
        self.store.clear()


class _Hat(BaseModel):
    name: str


@pytest.fixture
def file_backend(tmp_path):
    return FileCacheBackend(tmp_path / "cache", default_timeout=60)


class TestFileCacheBackend:
    def test_roundtrip_of_pydantic_model(self, file_backend):
        hat = _Hat(name="mont-blanc")
        file_backend.set("key-1", hat, timeout=60)
        result = file_backend.get("key-1")
        assert isinstance(result, _Hat)
        assert result == hat

    def test_miss_returns_default(self, file_backend):
        assert file_backend.get("nope") is None
        assert file_backend.get("nope", 42) == 42

    def test_cached_none_is_a_hit(self, file_backend):
        file_backend.set("none-key", None, timeout=60)
        assert file_backend.get("none-key", "missed") is None

    def test_ttl_expires_entry(self, tmp_path):
        backend = FileCacheBackend(tmp_path / "cache", default_timeout=1)
        backend.set("k", "v", timeout=0)  # expires immediately
        assert backend.get("k", "missed") == "missed"

    def test_survives_new_instance_on_same_directory(self, file_backend, tmp_path):
        file_backend.set("persist", _Hat(name=" persistence"), timeout=3600)
        reborn = FileCacheBackend(tmp_path / "cache")
        assert reborn.get("persist") == _Hat(name=" persistence")

    def test_clear_removes_entries(self, file_backend):
        file_backend.set("a", 1, timeout=60)
        file_backend.set("b", 2, timeout=60)
        file_backend.clear()
        assert file_backend.get("a", "missed") == "missed"
        assert file_backend.get("b", "missed") == "missed"


class TestCachedDecorator:
    @pytest.fixture(autouse=True)
    def isolated_default_backend(self, tmp_path):
        original = get_default_cache_backend()
        set_default_cache_backend(FileCacheBackend(tmp_path / "cache"))
        yield
        set_default_cache_backend(original)

    def test_second_call_hits_cache(self):
        calls = []

        @cached()
        def add(a: int, b: int = 1) -> int:
            calls.append((a, b))
            return a + b

        assert add(2) == 3
        assert add(2) == 3
        assert calls == [(2, 1)]

    def test_ignored_argument_not_in_key(self):
        calls = []

        @cached(ignore=["api_key"])
        def fetch(asset_id: int, api_key: str) -> str:
            calls.append(asset_id)
            return f"result-{asset_id}"

        assert fetch(1, "secret-one") == "result-1"
        assert fetch(1, "secret-two") == "result-1"  # same key despite different key
        assert calls == [1]

    def test_none_result_is_cached(self):
        calls = []

        @cached()
        def maybe(asset_id: int) -> None:
            calls.append(asset_id)
            return None

        assert maybe(1) is None
        assert maybe(1) is None
        assert calls == [1]

    def test_custom_backend_receives_values(self):
        dict_cache = DictCache()

        @cached(backend=dict_cache)
        def answer() -> int:
            return 42

        assert answer() == 42
        assert dict_cache.store and all(isinstance(k, str) for k in dict_cache.store)
        assert dict_cache.get(next(iter(dict_cache.store))) == 42

    def test_injecting_django_shaped_cache_globally(self):
        dict_cache = DictCache()
        set_default_cache_backend(dict_cache)
        calls = []

        @cached()
        def location(name: str) -> str:
            calls.append(name)
            return f"loc-{name}"

        assert location("chamonix") == "loc-chamonix"
        assert location("chamonix") == "loc-chamonix"
        assert calls == ["chamonix"]
        assert len(dict_cache.store) == 1
        clear_cache()
        assert dict_cache.store == {}

    def test_key_contains_package_version(self):
        dict_cache = DictCache()

        @cached(backend=dict_cache)
        def versioned() -> str:
            return "v"

        versioned()
        key = next(iter(dict_cache.store))
        assert key.startswith(cache_mod.package_version)
