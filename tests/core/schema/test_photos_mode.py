"""Offline tests for the tri-state PhotosMode (none / embedded / all)."""

import pytest

from hut_services import PhotoSchema, PhotosMode, normalize_photos_mode


def test_normalize_photos_mode() -> None:
    """Legacy bools and plain strings normalize to PhotosMode."""
    assert normalize_photos_mode(True) is PhotosMode.ALL
    assert normalize_photos_mode(False) is PhotosMode.NONE
    for mode in PhotosMode:
        assert normalize_photos_mode(mode) is mode
        assert normalize_photos_mode(mode.value) is mode


def test_normalize_photos_mode_invalid() -> None:
    """Unknown strings are rejected."""
    with pytest.raises(ValueError, match="sometimes"):
        normalize_photos_mode("sometimes")  # type: ignore[arg-type]


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


def test_camptocamp_photos_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """EMBEDDED (default) and NONE never fetch; only ALL makes the extra request."""
    from hut_services.camptocamp import schema as c2c_schema
    from hut_services.camptocamp.schema import (
        CamptocampDocument,
        CamptocampGeometry,
        CamptocampHut0Convert,
        CamptocampLocale,
    )

    doc = CamptocampDocument(
        document_id=1931266,
        version=1,
        locales=[CamptocampLocale(version=1, lang="sl", title="Koča na Pesku")],
        geometry=CamptocampGeometry(version=1, geom='{"type":"Point","coordinates":[913125,5850123]}'),
        associations={"images": [{"document_id": 167028}]},
    )

    calls: list[tuple[int, ...]] = []

    def fake_get_images(ids: tuple[int, ...]) -> list[PhotoSchema]:
        calls.append(ids)
        return [_photo(str(i)) for i in ids]

    monkeypatch.setattr(c2c_schema, "get_images", fake_get_images)

    # new default EMBEDDED: photos that are not part of the source data stay empty, no request
    assert CamptocampHut0Convert(source_data=doc).get_hut().photos == []
    assert calls == []

    # NONE and legacy False: same
    assert CamptocampHut0Convert(source_data=doc, include_photos=PhotosMode.NONE).get_hut().photos == []
    assert CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut().photos == []
    assert calls == []

    # ALL: fetches (one request per image, via get_images)
    hut = CamptocampHut0Convert(source_data=doc, include_photos=PhotosMode.ALL).get_hut()
    assert len(hut.photos) == 1
    assert hut.photos[0].raw_url  # type: ignore[union-attr]
    assert calls == [(167028,)]
