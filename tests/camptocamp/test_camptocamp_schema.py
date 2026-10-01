"""Offline converter tests (no API access)."""

from hut_services.camptocamp.schema import (
    CamptocampDocument,
    CamptocampGeometry,
    CamptocampHut0Convert,
    CamptocampLocale,
)


def _doc(lang: str, title: str, summary: str | None = None) -> CamptocampDocument:
    return CamptocampDocument(
        document_id=1931266,
        version=1,
        locales=[CamptocampLocale(version=1, lang=lang, title=title, summary=summary)],
        geometry=CamptocampGeometry(version=1, geom='{"type":"Point","coordinates":[913125,5850123]}'),
        elevation=1386,
    )


def test_convert_name_unsupported_locale() -> None:
    """The original name is kept even if its language is not de/en/fr/it (e.g. 'sl')."""
    hut = CamptocampHut0Convert(source_data=_doc("sl", "Koča na Pesku"), include_photos=False).get_hut()
    assert hut.name.de == "Koča na Pesku"
    assert hut.name.i18n == "Koča na Pesku"


def test_convert_name_supported_locale() -> None:
    """Supported languages are mapped to their slot (not the fallback)."""
    hut = CamptocampHut0Convert(source_data=_doc("fr", "Cabane de la Pesku"), include_photos=False).get_hut()
    assert hut.name.fr == "Cabane de la Pesku"
    assert hut.name.de == ""
    assert hut.name.i18n == "Cabane de la Pesku"


def test_convert_description_unsupported_locale() -> None:
    """The original description is kept even if its language is not de/en/fr/it."""
    hut = CamptocampHut0Convert(
        source_data=_doc("sl", "Koča na Pesku", summary="Lepa koča v Sloveniji"), include_photos=False
    ).get_hut()
    assert hut.description.i18n == "Lepa koča v Sloveniji"


def test_convert_url_and_source_link() -> None:
    """`url` is the hut website only (or empty); the camptocamp page link lives in `source`."""
    hut = CamptocampHut0Convert(source_data=_doc("sl", "Koča na Pesku"), include_photos=False).get_hut()
    assert hut.url == ""
    assert hut.source is not None
    assert hut.source.url == "https://www.camptocamp.org/waypoints/1931266"
    doc = _doc("sl", "Koča na Pesku")
    doc.url = "https://example.com"
    hut2 = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut2.url == "https://example.com"


def test_convert_web_mercator_location() -> None:
    """Leftover Web Mercator coordinates are converted to WGS84 (x=913125, y=5850123 -> ~46.43N 8.20E)."""
    hut = CamptocampHut0Convert(source_data=_doc("sl", "Koča na Pesku"), include_photos=False).get_hut()
    assert 46 < hut.location.lat < 47
    assert 8 < hut.location.lon < 9
