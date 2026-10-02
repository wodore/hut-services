"""Offline converter tests (no API access)."""

from hut_services.camptocamp.schema import (
    CamptocampDocument,
    CamptocampGeometry,
    CamptocampHut0Convert,
    CamptocampLocale,
)
from hut_services.core.schema import AnswerEnum, HutTypeEnum


def _doc(
    lang: str,
    title: str,
    summary: str | None = None,
    waypoint_type: str | None = None,
    elevation: int | None = None,
    capacity: int | None = None,
    capacity_staffed: int | None = None,
    access_period: str | None = None,
    custodianship: str | None = None,
) -> CamptocampDocument:
    return CamptocampDocument(
        document_id=1931266,
        version=1,
        locales=[CamptocampLocale(version=1, lang=lang, title=title, summary=summary, access_period=access_period)],
        geometry=CamptocampGeometry(version=1, geom='{"type":"Point","coordinates":[913125,5850123]}'),
        elevation=elevation,
        waypoint_type=waypoint_type,
        capacity=capacity,
        capacity_staffed=capacity_staffed,
        custodianship=custodianship,
    )


def test_convert_bivouac_stays_bivouac() -> None:
    """Camptocamp 'bivouac' is authoritative (waypoint 1925122 was 'shelter')."""
    doc = _doc(
        "it",
        "Bivacco Ambrogio Fogar all'Alpe Fornalino",
        waypoint_type="bivouac",
        elevation=2084,
        capacity=12,
    )
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.hut_type.if_open is HutTypeEnum.bivouac
    assert hut.hut_type.if_closed is None  # no access period data -> not known to be seasonal
    assert hut.capacity.if_open == 12  # unstaffed capacity is the open capacity
    assert hut.capacity.if_closed is None


def test_convert_staffed_hut_capacity_and_reduced_type() -> None:
    """capacity_staffed is the open capacity, capacity the winter (closed) one."""
    doc = _doc(
        "fr",
        "Cabane Hollandia",
        waypoint_type="hut",
        elevation=2400,
        capacity=30,
        capacity_staffed=100,
        access_period="Mi-mars à fin mai et juillet à début septembre",
    )
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.capacity.if_open == 100
    assert hut.capacity.if_closed == 30
    assert hut.hut_type.if_open is HutTypeEnum.hut
    assert hut.hut_type.if_closed is HutTypeEnum.selfhut  # reduced type from the smaller winter number


def test_convert_seasonal_without_second_capacity() -> None:
    """Seasonal hut without a second capacity number gets 'unknown' as reduced type."""
    doc = _doc("fr", "Cabane Test", waypoint_type="hut", elevation=2400, access_period="juillet à septembre")
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.hut_type.if_closed is HutTypeEnum.unknown


def test_convert_gite_is_bhotel_closed_when_wardened() -> None:
    """A gite is a 'bhotel' and 'gardé, fermé hors gardiennage' means closed otherwise (waypoint 1933757)."""
    doc = _doc(
        "fr",
        "Refuge de Becchi Rossi",
        waypoint_type="gite",
        elevation=1900,
        access_period="Je pense que la route est fermée l'hiver (?)",
        custodianship="accessible_when_wardened",
    )
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.hut_type.if_open is HutTypeEnum.bhotel
    assert hut.hut_type.if_closed is HutTypeEnum.closed


def test_convert_hotel_like_seasonal_closed() -> None:
    """bhotel, hostel and hotel simply close outside their season."""
    doc = _doc("fr", "Gîte du Test", waypoint_type="gite", elevation=1900, access_period="juillet à septembre")
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.hut_type.if_open is HutTypeEnum.bhotel
    assert hut.hut_type.if_closed is HutTypeEnum.closed


def test_convert_year_round_no_reduced_type() -> None:
    """A hut open all year has no reduced type."""
    doc = _doc("fr", "Cabane Test", waypoint_type="hut", elevation=2400, access_period="Toute l'année")
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.hut_type.if_closed is None


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


def test_convert_open_monthly() -> None:
    """Opening months are parsed from the free text access period."""
    doc = _doc("fr", "Cabane Hollandia")
    doc.locales[0].access_period = "Mi-mars à fin mai et juillet à début septembre"
    hut = CamptocampHut0Convert(source_data=doc, include_photos=False).get_hut()
    assert hut.open_monthly[3] is AnswerEnum.yesish
    assert hut.open_monthly[4] is AnswerEnum.yes
    assert hut.open_monthly[6] is AnswerEnum.unknown
    assert hut.open_monthly[9] is AnswerEnum.yesish
    assert hut.open_monthly.url == "https://www.camptocamp.org/waypoints/1931266"


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
