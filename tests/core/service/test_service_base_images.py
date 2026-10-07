"""Tests for the BaseService image methods (get_images / get_images_many)."""

import time

import pytest

from hut_services import BaseService, PhotoSchema
from hut_services.core.schema import SourceDataSchema


class _NoImagesService(BaseService):
    """Service without image access."""


class _FakeSourceData(SourceDataSchema):
    def get_id(self) -> str:
        return "1"

    def get_name(self) -> str:
        return "Fake"


def _photo(ident: str) -> PhotoSchema:
    return PhotoSchema(
        raw_url=f"https://example.com/{ident}.jpg",
        url=f"https://example.com/{ident}",
        source=None,
        author=None,
        licenses=[],
        width=100,
        height=100,
        capture_date=None,
        comment="",
    )


class _ImagesService(BaseService):
    """Service whose get_images takes 50ms per id (sleeps, no network)."""

    def get_images(self, source_id: int | str) -> list[PhotoSchema]:
        time.sleep(0.05)
        if source_id == "empty":
            return []
        return [_photo(str(source_id))]


def test_get_images_not_implemented() -> None:
    service = _NoImagesService()
    with pytest.raises(NotImplementedError, match="get_images"):
        service.get_images(1)
    with pytest.raises(NotImplementedError, match="get_images"):
        service.get_images_many([1, 2])


def test_get_images_many_parallel() -> None:
    """8 ids at 50ms each run in parallel (well under 8x50ms) and map back correctly."""
    service = _ImagesService()
    ids = list(range(8))
    t0 = time.monotonic()
    result = service.get_images_many(ids, max_workers=8)  # type: ignore[arg-type]
    dt = time.monotonic() - t0
    assert set(result) == set(ids)
    assert result[3] == [_photo("3")]
    assert dt < 8 * 0.05, f"not parallel: {dt:.2f}s"
    assert service.get_images_many([], max_workers=4) == {}
    assert (
        service.get_images_many(["empty"])[  # type: ignore[list-item]
            "empty"
        ]
        == []
    )


def test_get_images_many_many_ids_capped() -> None:
    """More ids than workers still completes (workers capped, not exceeded)."""
    service = _ImagesService()
    ids = [f"hut-{i}" for i in range(20)]
    result = service.get_images_many(ids, max_workers=4)  # type: ignore[arg-type]
    assert len(result) == 20
    assert result["hut-19"] == [_photo("hut-19")]
