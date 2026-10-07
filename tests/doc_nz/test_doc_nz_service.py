"""Tests for the DOC New Zealand hut source.

Online tests hit the live DOC open-data FeatureServer (no key needed) and
are skipped when it is unreachable. Conversion tests run offline against
canned layer data.
"""

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
    "hutCategory": "Standard hut",
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
        return service.get_huts_from_source(limit=HUT_LIMIT)
    except OSError as e:  # httpx network errors derive from OSError
        pytest.skip(f"DOC FeatureServer not usable from this environment, skipping: {e!r}")


@pytest.fixture(scope="module")
def huts(service: DocNzService) -> list[HutSchema]:
    try:
        return service.get_huts(limit=HUT_LIMIT)
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
    assert detail.hut_category == "Standard hut"
    assert detail.introduction is not None and detail.introduction.startswith("A standard")


def test_doc_nz_category_mapping() -> None:
    assert get_hut_category(None) == Cat.unknown
    assert get_hut_category("Great Walks Hut") == Cat.great_walk
    assert get_hut_category("Serviced Hut") == Cat.serviced
    assert get_hut_category("Standard hut") == Cat.standard
    assert get_hut_category("Basic Hut") == Cat.basic
    assert get_hut_category("Bivvy or Basic hut") == Cat.bivvy


def test_doc_nz_convert_offline() -> None:
    """Conversion to HutSchema works with base layer data only."""
    hut_src = DocNzHutSource(
        name="Mcintosh Hut",
        source_data=DocNzHutSchema.model_validate(CANNED_FEATURE),
        source_id="100040290",
        location=DocNzHutSchema.model_validate(CANNED_FEATURE).get_location(),
        source_properties=DocNzProperties(bookable=False, region="Otago", place="Whakaari", hut_category=None),
    )
    hut = DocNzHut0Convert(source_data=hut_src.source_data, include_photos=False).get_hut()  # type: ignore[arg-type]
    assert type(hut) is HutSchema
    assert hut.name.en == "Mcintosh Hut"
    assert hut.country_code == "nz"
    assert hut.url.startswith("https://www.doc.govt.nz/link/")
    assert hut.source is not None and hut.source.ident == "100040290"
    assert hut.license is not None and hut.license.slug == "CC-BY-4.0"
    assert hut.owner is not None and "Department of Conservation" in hut.owner.name
    assert hut.capacity.if_open is None  # bunks need the DOC API
    assert hut.extras["bookable"] is False
    assert "Heating" in hut.extras["facilities"]
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
    assert hut.extras["hut_category"] == "Standard hut"


def test_doc_nz_convert_great_walk_offline() -> None:
    """Great Walk huts convert to attended 'hut' type."""
    great_walk = {**CANNED_FEATURE, "hutCategory": "Great Walks Hut", "numberOfBunks": 40, "bookable": "Yes"}
    hut = DocNzHut0Convert(source_data=DocNzHutSchema.model_validate(great_walk), include_photos=False).get_hut()
    assert hut.hut_type.if_open.value == "hut"
    assert hut.capacity.if_open == 40
    assert hut.extras["bookable"] is True


def test_doc_nz_service_enrich_without_key() -> None:
    """`enrich=True` without an API key raises (explicit demand, not a silent fallback)."""
    no_key_service = DocNzService(api_key=None)
    import os

    old = os.environ.pop("DOC_NZ_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="DOC API key required"):
            no_key_service.get_huts_from_source(limit=1, enrich=True)
    finally:
        if old is not None:
            os.environ["DOC_NZ_API_KEY"] = old


def test_doc_nz_alerts_without_key() -> None:
    no_key_service = DocNzService(api_key=None)
    import os

    old = os.environ.pop("DOC_NZ_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="DOC API key required"):
            no_key_service.get_alerts()
    finally:
        if old is not None:
            os.environ["DOC_NZ_API_KEY"] = old


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
