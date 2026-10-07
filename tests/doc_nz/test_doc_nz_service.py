"""Tests for the DOC New Zealand hut source.

Online tests hit the live DOC open-data FeatureServer (no key needed) and
are skipped when it is unreachable. Conversion tests run offline against
canned layer data.
"""

import os
import typing as t

import pytest

from hut_services.core.schema import HutSchema
from hut_services.doc_nz import DocNzService
from hut_services.doc_nz.schema import (
    DocNzHut0Convert,
    DocNzHutSchema,
    DocNzHutSource,
    DocNzProperties,
    get_hut_category,
)
from hut_services.doc_nz.schema import (
    HutCategoryEnum as Cat,
)

HUT_LIMIT: int = 2

#: Canned FeatureServer feature (attributes + WGS84 point geometry), offline test data.
CANNED_FEATURE: dict = {
    "OBJECTID": 621574,
    "name": "Mcintosh Hut",
    "place": "Whakaari Conservation Area",
    "region": "Otago",
    "bookable": "No",
    "facilities": "Heating, Mattresses, Toilets - non-flush, Water from tap - not treated",
    "hasAlerts": "Refer to DOC website for current alerts",
    "introductionThumbnail": "https://www.doc.govt.nz/thumbs/large/link/2fde126d2d8f4a2488d19c960e7f423d.aspx",
    "staticLink": "https://www.doc.govt.nz/link/3e768c88dab541fe9f3082b3194206fa.aspx",
    "locationString": "Whakaari Conservation Area",
    "assetId": 100040290,
    "dateLoadedToGIS": 1776160604000,
    "GlobalID": "38fac8fc-f481-4d4c-a551-0577952ccf73",
    "lat": -44.83166095268654,
    "lon": 168.45639649417328,
}

#: Same hut enriched with DOC API v2 detail fields (offline test data).
CANNED_DETAIL: dict = {
    "numberOfBunks": 10,
    "hutCategory": "Standard",
    "proximityToRoadEnd": "2 hr walk",
    "introduction": "A standard six-bunk hut in the Landsborough.",
    "status": "OPEN",
}


@pytest.fixture(scope="module")
def service() -> DocNzService:
    # no fake key: with auto-enrichment a bogus key would fire useless
    # detail requests (gracefully ignored, but pointless)
    return DocNzService()


@pytest.fixture(scope="module")
def hut_sources(service: DocNzService) -> list[DocNzHutSource]:
    try:
        # include_campsites=False guarantees hut-only results (typed as the union otherwise)
        return t.cast(
            "list[DocNzHutSource]",
            service.get_huts_from_source(limit=HUT_LIMIT, include_campsites=False),
        )
    except OSError as e:  # httpx network errors derive from OSError
        pytest.skip(f"DOC FeatureServer not usable from this environment, skipping: {e!r}")


@pytest.fixture(scope="module")
def huts(service: DocNzService) -> list[HutSchema]:
    try:
        return service.get_huts(limit=HUT_LIMIT, include_campsites=False)
    except OSError as e:
        pytest.skip(f"DOC FeatureServer not usable from this environment, skipping: {e!r}")


def test_doc_nz_schema_parsing() -> None:
    """Layer attributes parse into the source schema ("Yes"/"No", facilities, epoch ms)."""
    hut = DocNzHutSchema.model_validate(CANNED_FEATURE)
    assert hut.asset_id == 100040290
    assert hut.get_id() == "100040290"
    assert hut.get_name() == "Mcintosh Hut"
    assert hut.bookable is False
    assert hut.facilities is not None and "Heating" in hut.facilities
    assert hut.static_link is not None and hut.static_link.startswith("https://www.doc.govt.nz/link/")
    assert hut.date_loaded is not None and hut.date_loaded.year == 2026
    assert hut.get_location().lat == pytest.approx(-44.8317, abs=1e-4)
    assert hut.get_location().lon == pytest.approx(168.4564, abs=1e-4)


def test_doc_nz_schema_detail_merge() -> None:
    """DOC API detail fields enrich the layer hut."""
    hut = DocNzHutSchema.model_validate(CANNED_FEATURE)
    detail = DocNzHutSchema.model_validate({**CANNED_FEATURE, **CANNED_DETAIL})
    assert hut.number_of_bunks is None
    assert detail.number_of_bunks == 10
    assert detail.hut_category == "Standard"
    assert detail.introduction is not None and detail.introduction.startswith("A standard")


def test_doc_nz_category_mapping() -> None:
    assert get_hut_category(None) == Cat.unknown
    # real API vocabulary (sampled 2026-10): "Great Walk", "Serviced", "Standard", "Basic/bivvies"
    assert get_hut_category("Great Walk") == Cat.great_walk
    assert get_hut_category("Serviced") == Cat.serviced
    assert get_hut_category("Standard") == Cat.standard
    assert get_hut_category("Basic/bivvies") == Cat.basic  # combined category, NOT bivvy
    assert get_hut_category("Bivvy or Basic hut") == Cat.bivvy  # standalone bivvy category
    assert get_hut_category(None) == Cat.unknown


def test_doc_nz_convert_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Conversion to HutSchema works with base layer data only."""
    from hut_services.doc_nz import schema as doc_schema

    monkeypatch.setattr(doc_schema, "get_hut_images", lambda s: [])
    monkeypatch.setattr(doc_schema, "get_hut_website", lambda s: "")
    hut_src = DocNzHutSource(
        name="Mcintosh Hut",
        source_data=DocNzHutSchema.model_validate(CANNED_FEATURE),
        source_id="100040290",
        location=DocNzHutSchema.model_validate(CANNED_FEATURE).get_location(),
        source_properties=DocNzProperties(
            bookable=False, region="Otago", place="Whakaari", hut_category=None, page_uuid=None
        ),
    )
    hut = DocNzHut0Convert(source_data=hut_src.source_data, include_photos=False).get_hut()  # type: ignore[arg-type]
    assert type(hut) is HutSchema
    assert hut.name.en == "Mcintosh Hut"
    assert hut.country_code == "nz"
    assert hut.url == ""  # no website link in the (patched) page body; the doc page lives on source.url
    assert hut.source is not None and hut.source.ident == "100040290"
    assert hut.license is not None and hut.license.slug == "cc-by-4.0"
    assert hut.owner is not None and "Department of Conservation" in hut.owner.name
    assert hut.capacity.if_open is None  # bunks need the DOC API
    assert hut.extras["bookable"] is False
    assert "Heating" in hut.extras["facilities"]
    assert hut.notes and hut.notes[0].en.startswith("Facilities: ")  # human-readable facilities note
    assert hut.is_bookable is False  # no booking service in the public source


def test_doc_nz_convert_enriched_offline() -> None:
    """With detail data: bunks map to capacity, category to hut type, intro to description."""
    enriched = DocNzHutSchema.model_validate({**CANNED_FEATURE, **CANNED_DETAIL})
    hut = DocNzHut0Convert(source_data=enriched, include_photos=False).get_hut()
    assert hut.capacity.if_open == 10
    assert hut.hut_type.if_open.value == "selfhut"  # Standard hut -> unattended
    assert hut.description.en is not None and hut.description.en.startswith("A standard")
    assert hut.author is not None
    assert hut.is_active is True
    assert hut.extras["hut_category"] == "Standard"


def test_doc_nz_convert_basic_bivvies_offline() -> None:
    """'Basic/bivvies' stays selfhut (the model's bivouac implies altitude, NZ bivs have none)."""
    basic = {**CANNED_FEATURE, "hutCategory": "Basic/bivvies", "numberOfBunks": 4}
    hut = DocNzHut0Convert(source_data=DocNzHutSchema.model_validate(basic), include_photos=False).get_hut()
    assert hut.hut_type.if_open.value == "selfhut"
    biv_named = {**basic, "name": "Candlesticks Biv"}
    hut2 = DocNzHut0Convert(source_data=DocNzHutSchema.model_validate(biv_named), include_photos=False).get_hut()
    assert hut2.hut_type.if_open.value == "selfhut"  # guess: elevation < 2200 -> selfhut


def test_doc_nz_convert_closed_status_offline() -> None:
    """Closed huts report is_active=False (real vocabulary: 'OPEN'/'CLSD')."""
    closed = {**CANNED_FEATURE, "status": "CLSD"}
    hut = DocNzHut0Convert(source_data=DocNzHutSchema.model_validate(closed), include_photos=False).get_hut()
    assert hut.is_active is False
    open_hut = DocNzHut0Convert(
        source_data=DocNzHutSchema.model_validate({**CANNED_FEATURE, **CANNED_DETAIL}), include_photos=False
    ).get_hut()
    assert open_hut.is_active is True


def test_doc_nz_convert_great_walk_offline() -> None:
    """Great Walk huts convert to attended 'hut' type."""
    great_walk = {**CANNED_FEATURE, "hutCategory": "Great Walk", "numberOfBunks": 40, "bookable": "Yes"}
    hut = DocNzHut0Convert(source_data=DocNzHutSchema.model_validate(great_walk), include_photos=False).get_hut()
    assert hut.hut_type.if_open.value == "hut"
    assert hut.capacity.if_open == 40
    assert hut.extras["bookable"] is True


def test_doc_nz_service_enrich_without_key() -> None:
    """`enrich=True` without an API key raises (explicit demand, not a silent fallback)."""
    no_key_service = DocNzService(api_key=None)

    old = os.environ.pop("HUT_SRV_DOC_NZ_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="DOC API key required"):
            no_key_service.get_huts_from_source(limit=1, enrich=True)
    finally:
        if old is not None:
            os.environ["HUT_SRV_DOC_NZ_API_KEY"] = old


def test_doc_nz_alerts_without_key() -> None:
    no_key_service = DocNzService(api_key=None)

    old = os.environ.pop("HUT_SRV_DOC_NZ_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="DOC API key required"):
            no_key_service.get_alerts()
    finally:
        if old is not None:
            os.environ["HUT_SRV_DOC_NZ_API_KEY"] = old


def test_doc_nz_service_includes_campsites_online(service: DocNzService) -> None:
    """Default call returns huts AND campsites; both convert through the same service."""
    try:
        sources = service.get_huts_from_source(limit=1)
    except OSError as e:
        pytest.skip(f"DOC FeatureServer not usable from this environment, skipping: {e!r}")
    source_types = {type(s).__name__ for s in sources}
    assert "DocNzHutSource" in source_types
    assert "DocNzCampsiteHutSource" in source_types
    for src in sources:
        hut = service.convert(src.model_dump(by_alias=True))
        assert type(hut) is HutSchema


def test_doc_nz_service_source_online(hut_sources: list[DocNzHutSource]) -> None:
    """Get huts from the DOC FeatureServer."""
    assert len(hut_sources) == HUT_LIMIT
    for h in hut_sources:
        print(h.show(source_name=False))
        assert type(h) is DocNzHutSource
        assert h.source_properties is not None and h.source_properties.bookable is not None


def test_doc_nz_service_hut_online(huts: list[HutSchema]) -> None:
    """Tests conversion to HutSchema as well."""
    assert len(huts) == HUT_LIMIT
    assert type(huts[0]) is HutSchema
    for hut in huts:
        assert hut.country_code == "nz"


def test_doc_nz_service_convert_dict_online(hut_sources: list[DocNzHutSource], service: DocNzService) -> None:
    """Convert by a dict."""
    for h in hut_sources:
        h_dict = h.model_dump(by_alias=True)
        hut = service.convert(h_dict)
        assert type(hut) is HutSchema
        assert hut.name.en != ""


def test_doc_nz_parse_page_images() -> None:
    """Hero + gallery parsing with license rules ((c) skipped, CC/DOC kept)."""
    from hut_services.doc_nz import images

    canned = (
        '<section class="doc-main-layout__hero">'
        '<div class="hero__top-caption"><doc-image-caption caption="Ellis Hut">'
        '<div class="hide-content"><span><b>Image: </b></span> Ian Wright <span> | &copy;</span></div>'
        "</doc-image-caption></div>"
        '<picture><source srcset="/thumbs/hero/contentassets/08c2bcb0cd644a7fa0f375cea329ae2c/ellis-hut-1067.jpg"/>'
        '<img src="/thumbs/hero/contentassets/08c2bcb0cd644a7fa0f375cea329ae2c/ellis-hut-1067.jpg" alt="Ellis Hut.">'
        "</picture></section>"
        '<doc-fancy-image src="/globalassets/images/a/view-1200.jpg" '
        'caption="Mt Cook from Mueller Hut Image: Robert Gr&ouml;tschel | &lt;a href=&quot; /footer-links/copyright/&quot; target=&quot;_blank&quot;&gt;DOC&lt;/a&gt;">'
        '<doc-image alt="Mt Cook from Mueller Hut. " src="/thumbs/gallery/globalassets/images/a/view-1200.jpg">'
        "</doc-image></doc-fancy-image>"
        '<doc-fancy-image src="/globalassets/images/b/winter-1200.jpg" '
        'caption="Mueller Hut winter Image: Jamie Blyth | &lt;a href=&quot;https://creativecommons.org/licenses/by-nc/4.0/&quot; target=&quot;_blank&quot;&gt;Creative Commons&lt;/a&gt;">'
        '<doc-image alt="Mueller Hut winter." src="/thumbs/gallery/globalassets/images/b/winter-1200.jpg">'
        "</doc-image></doc-fancy-image>"
        '<doc-fancy-image src="/globalassets/images/c/protected-1200.jpg" '
        'caption="Some photo Image: A Photographer">'
        '<doc-image alt="Some photo." src="/thumbs/gallery/globalassets/images/c/protected-1200.jpg">'
        "</doc-image></doc-fancy-image>"
    )
    photos = images.parse_page_images(
        canned, "https://www.doc.govt.nz/real/huts/test-hut/", "https://www.doc.govt.nz/link/abc.aspx"
    )
    assert len(photos) == 2  # hero ((c)) and unlicensed gallery photo skipped
    doc_photo, cc_photo = photos
    assert doc_photo.raw_url == "https://www.doc.govt.nz/globalassets/images/a/view-1200.jpg"
    assert doc_photo.licenses[0].slug == "cc-by-4.0"  # DOC = Crown CC BY 4.0
    assert doc_photo.author is not None and doc_photo.author.name == "Robert Grötschel"
    assert doc_photo.caption.en == "Mt Cook from Mueller Hut"
    assert str(doc_photo.url) == "https://www.doc.govt.nz/real/huts/test-hut/"
    assert cc_photo.licenses[0].slug == "cc-by-nc-4.0"  # exact CC license from the link
    assert cc_photo.author is not None and cc_photo.author.name == "Jamie Blyth"


def test_doc_nz_photos_online() -> None:
    """Live: the Mueller Hut page yields photos with licenses."""
    import pytest as _pytest

    from hut_services.doc_nz.images import get_hut_images

    try:
        photos = get_hut_images("https://www.doc.govt.nz/link/ca3bf5da422f462781809b92757e7278.aspx")
    except Exception as e:  # network/HTTP errors -> skip
        _pytest.skip(f"doc.govt.nz not reachable: {e!r}")
    assert len(photos) >= 2
    for photo in photos:
        assert photo.licenses, "every included photo must carry a license"
    assert any(p.licenses[0].slug == "cc-by-4.0" for p in photos)


def test_doc_nz_get_images_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_images resolves the assetId to a page link, independent of conversion."""
    from hut_services.core.schema import PhotoSchema
    from hut_services.doc_nz import service as doc_service

    canned = PhotoSchema(
        raw_url="https://www.doc.govt.nz/globalassets/x-1200.jpg",
        url="https://www.doc.govt.nz/real/huts/x/",
        source=None,
        author=None,
        licenses=[],
        width=1200,
        height=800,
        capture_date=None,
        comment="",
    )
    monkeypatch.setattr(
        doc_service, "_static_link_for", lambda aid: "https://www.doc.govt.nz/link/abc.aspx" if aid == 42 else None
    )
    monkeypatch.setattr(doc_service, "get_hut_images", lambda s: [canned])
    service = DocNzService()
    assert service.get_images(42) == [canned]
    assert service.get_images("42") == [canned]  # str ids accepted
    assert service.get_images(999) == []  # unknown -> [] (warning logged)
    assert service.get_images("not-an-id") == []


def test_doc_nz_get_images_online() -> None:
    """Live: Mueller Hut (assetId 100040842) has licensed photos."""
    service = DocNzService()
    try:
        photos = service.get_images(100040842)
    except OSError as e:
        pytest.skip(f"DOC not reachable: {e!r}")
    assert len(photos) >= 2
    assert all(p.licenses for p in photos)


def test_doc_nz_extract_website() -> None:
    """External website links come from the page body text; junk domains are skipped."""
    from hut_services.doc_nz.images import _extract_website

    canned = (
        '<doc-body-text><div><p><a href="https://maps.google.com/maps">Directions</a>. '
        "Privately owned, managed by Rakiura Maori Lands Trust. "
        '<a href="https://rmlt.co.nz/hunting/">See the Rakiura Maori Lands Trust website</a>.</p></div></doc-body-text>'
    )
    assert _extract_website(canned) == "https://rmlt.co.nz/hunting/"  # google link skipped
    assert _extract_website("<doc-body-text><p>No links here.</p></doc-body-text>") == ""
    assert _extract_website("<p>Link outside the body: <a href='https://x.example.com/'>x</a></p>") == ""


def test_doc_nz_hut_website_online() -> None:
    """Live: Chew Tobacco Hunters Hut links its manager's website (rmlt.co.nz)."""
    from hut_services.doc_nz.images import get_hut_website

    try:
        url = get_hut_website("https://www.doc.govt.nz/link/1b3d9da012a3464688f3ebe4982ec653.aspx")
    except Exception as e:
        pytest.skip(f"doc.govt.nz not reachable: {e!r}")
    assert url == "http://www.rmlt.co.nz/hunting/"  # the contact panel's Website row
