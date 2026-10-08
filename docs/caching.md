# Caching

All requests to external services are cached. The default backend is a file
cache; any Django-style cache (database, Redis, memcached, ...) can replace it
process-wide.

## Configuration

The default file cache is controlled with environment variables:

| Variable                     | Default                          | Description               |
| ---------------------------- | -------------------------------- | ------------------------- |
| `HUT_SERVICE_CACHE_DIR`      | `<tempdir>/py_file_cache`        | Cache directory           |
| `HUT_SERVICE_EXPIRE_SECONDS` | `172800` (2 days)                | Default entry lifetime    |

## Cached functions

Decorate a module-level function with [`cached`][hut_services.core.cache.cached]
to cache its return values. Cache keys are derived from the package version,
the function name and its arguments, so entries do not survive library
upgrades. Arguments listed in `ignore` (secrets, client objects) are excluded
from the key.

```python
from hut_services.core.cache import cached


@cached(ignore=["api_key"], expire_in_seconds=3600 * 24)
def get_hut(asset_id: int, api_key: str) -> dict:
    ...


@cached(ignore=["client"], forever=True)  # 10-year timeout
def get_photo(client, qid: str) -> Photo | None:
    ...
```

`clear_cache()` (or `BaseService.clear_all_cache()`) empties the default
backend.

### Evicting single entries

A cached function exposes an `evict()` helper with the same signature as the
function. It deletes exactly the entry a call with these arguments would read
— via the backend's standard `delete(key)`, so it works with any conforming
backend, including Django caches:

```python
@cached(ignore=["sync_client"])
def get_hut(hut_id: int, sync_client=None) -> dict:
    ...


data = get_hut(42)
if not data:  # e.g. a failed request was cached as an empty dict
    get_hut.evict(42)  # next call re-fetches hut 42, all other entries survive
```

Arguments listed in `ignore` are excluded from the eviction key just as they
are from the cache key. Evicting *all* entries of a function is deliberately
not supported: Django's `BaseCache` cannot enumerate keys (`delete_pattern`
only exists on some backends) — use `clear_cache()` for that.

## Custom backends

Any object implementing
[`CacheBackend`][hut_services.core.cache.CacheBackend] — `get(key, default)`,
`set(key, value, timeout)`, `clear()` — can replace the default. This matches
Django's `BaseCache` API, so a Django cache can be injected as-is:

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "hut_services_cache",
    }
}
# then: python manage.py createcachetable
```

```python
# apps.py
from django.apps import AppConfig
from django.core.cache import cache

from hut_services.core.cache import set_default_cache_backend


class HutConfig(AppConfig):
    def ready(self) -> None:
        set_default_cache_backend(cache)  # BaseCache conforms to CacheBackend
```

With the database backend the cache survives container restarts and is shared
across workers. Observed entry sizes are small enough (well under 1 MB) for
comfortable database storage.
