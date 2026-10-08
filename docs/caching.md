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

!!! note
    `file_cache` and `clear_file_cache` are deprecated aliases of `cached` and
    `clear_cache` and will be removed in a future release.
