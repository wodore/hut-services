"""Tests for the DOC New Zealand campsite source.

Online tests hit the live DOC open-data FeatureServer (no key needed) and
are skipped when it is unreachable. Conversion tests run offline against
canned layer data (trimmed from a live response).
"""

import pytest

from hut_services.core.schema import HutSchema, HutTypeEnum
from hut_services.doc_nz import DocNzCampsiteService
from hut_services.doc_nz.schema import (
    DocNzCampsite0Convert,
    DocNzCampsiteHutSource,
    DocNzCampsiteSchema,
    get_campsite_hut_type,
)

HUT_LIMIT: int = 2

#: Canned FeatureServer feature (trimmed from a live response), offline test data.
CANNED_CAMPSITE: dict = {
    "OBJECTID": 191598,
    "name": "Kiosk Creek Campsite",
    "place": "Fiordland National Park",
    "region": "Fiordland",
    "introduction": "There are spectacular views of glacial moraine deposits at this Fiordland campsite.",
    "campsiteCategory": "Standard",
    "numberOfPoweredSites": 0,
    "numberOfUnpoweredSites": 10,
    "bookable": "Yes",
    "free": None,
    "facilities": "Fire pit/place for campfires (except in fire bans), Non-powered/tent sites, Toilets - non-flush, Toilets",
    "activities": None,
    "dogsAllowed": 'No dogs. <a href="https://www.doc.govt.nz/parks-and-recreation/know-before-you-go/">Dogs on DOC land</a>.',
    "access": "Campervan, Car, Caravan",
    "hasAlerts": "Refer to DOC website for current alerts",
    "introductionThumbnail": "https://www.doc.govt.nz/thumbs/large/link/abb47a31f10d4eaea63ca1547351fb29.aspx",
    "staticLink": "https://www.doc.govt.nz/link/48d5461385ce4e75a35bd2e1254dfc6f.aspx",
    "locationString": "Located in Fiordland National Park",
    "x": 1207153,  # NZTM, ignored (geometry wins)
    "y": 5009087,
    "assetId": 100065488,
    "dateLoadedToGIS": 1776762092000,
    "GlobalID": "dc0656da-a070-453b-a6c3-c295e3697954",
    "lat": -44.962912665439106,
    "lon": 168.01882347049286,
}


@pytest.fixture(scope="module")
def service() -> DocNzCampsiteService:
    return DocNzCampsiteService()


@pytest.fixture(scope="module")
def sources(service: DocNzCampsiteService) -> list[DocNzCampsiteHutSource]:
    try:
        return service.get_huts_from_source(limit=HUT_LIMIT)
    except OSError as e:  # httpx network errors derive from OSError
        pytest.skip(f"DOC FeatureServer not usable from this environment, skipping: {e!r}")


@pytest.fixture(scope="module")
def huts(service: DocNzCampsiteService) -> list[HutSchema]:
    try:
        return service.get_huts(limit=HUT_LIMIT)
    except OSError as e:
        pytest.skip(f"DOC FeatureServer not usable from this environment, skipping: {e!r}")


def test_doc_nz_campsite_schema_parsing() -> None:
    """Layer attributes parse into the source schema."""
    campsite = DocNzCampsiteSchema.model_validate(CANNED_CAMPSITE)
    assert campsite.asset_id == 100065488
    assert campsite.get_id() == "100065488"
    assert campsite.get_name() == "Kiosk Creek Campsite"
    assert campsite.bookable is True
    assert campsite.campsite_category == "Standard"
    assert campsite.number_of_powered_sites == 0
    assert campsite.number_of_unpowered_sites == 10
    assert campsite.facilities is not None and "Toilets - non-flush" in campsite.facilities
    assert campsite.access is not None and "Campervan" in campsite.access
    assert campsite.date_loaded is not None and campsite.date_loaded.year == 2026
    assert campsite.get_location().lat == pytest.approx(-44.9629, abs=1e-4)


def test_doc_nz_campsite_convert_offline() -> None:
    """Conversion to HutSchema with layer data only."""
    campsite = DocNzCampsiteSchema.model_validate(CANNED_CAMPSITE)
    hut = DocNzCampsite0Convert(source_data=campsite, include_photos=False).get_hut()
    assert type(hut) is HutSchema
    assert hut.name.en == "Kiosk Creek Campsite"
    assert hut.country_code == "nz"
    assert hut.url.startswith("https://www.doc.govt.nz/link/")
    assert hut.source is not None and hut.source.ident == "100065488"
    assert hut.license is not None and hut.license.slug == "CC-BY-4.0"
    assert hut.description.en is not None and hut.description.en.startswith("There are spectacular views")
    assert hut.capacity.if_open is None and hut.capacity.if_closed is None  # capacity intentionally not mapped
    assert hut.extras["bookable"] is True
    assert hut.extras["powered_sites"] == 0
    assert hut.extras["unpowered_sites"] == 10
    assert "Toilets - non-flush" in hut.extras["facilities"]
    assert "<a href" not in hut.extras["dogs_allowed"]  # HTML stripped
    assert hut.notes and hut.notes[0].en.startswith("Facilities: ")
    assert hut.is_bookable is False  # no booking service in the public source
    assert hut.hut_type.if_open.value == "camping"  # Standard -> camping


def test_doc_nz_campsite_hut_type_mapping() -> None:
    """Managed and standard categories -> camping, rustic ones -> campgr."""
    assert get_campsite_hut_type("Great Walk").if_open == HutTypeEnum.camping
    assert get_campsite_hut_type("Serviced").if_open == HutTypeEnum.camping
    assert get_campsite_hut_type("Standard").if_open == HutTypeEnum.camping
    assert get_campsite_hut_type("Basic").if_open == HutTypeEnum.campgr
    assert get_campsite_hut_type("Backcountry").if_open == HutTypeEnum.campgr
    assert get_campsite_hut_type(None).if_open == HutTypeEnum.campgr
    great_walk = DocNzCampsite0Convert(
        source_data=DocNzCampsiteSchema.model_validate({**CANNED_CAMPSITE, "campsiteCategory": "Great Walk"}),
        include_photos=False,
    ).get_hut()
    assert great_walk.hut_type.if_open.value == "camping"


def test_doc_nz_campsite_closed_status_offline() -> None:
    """Closed campsites report is_active=False (enriched status 'CLSD')."""
    closed = DocNzCampsite0Convert(
        source_data=DocNzCampsiteSchema.model_validate({**CANNED_CAMPSITE, "status": "CLSD"}),
        include_photos=False,
    ).get_hut()
    assert closed.is_active is False


def test_doc_nz_campsite_enrich_without_key() -> None:
    """`enrich=True` without an API key raises (explicit demand)."""
    import os

    no_key_service = DocNzCampsiteService(api_key=None)
    old = os.environ.pop("HUT_SRV_DOC_NZ_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="DOC API key required"):
            no_key_service.get_huts_from_source(limit=1, enrich=True)
    finally:
        if old is not None:
            os.environ["HUT_SRV_DOC_NZ_API_KEY"] = old


def test_doc_nz_campsite_source_online(sources: list[DocNzCampsiteHutSource]) -> None:
    """Get campsites from the DOC FeatureServer."""
    assert len(sources) == HUT_LIMIT
    for s in sources:
        print(s.show(source_name=False))
        assert type(s) is DocNzCampsiteHutSource
        assert s.source_properties is not None and s.source_properties.bookable is not None


def test_doc_nz_campsite_hut_online(huts: list[HutSchema]) -> None:
    """Tests conversion to HutSchema as well."""
    assert len(huts) == HUT_LIMIT
    assert type(huts[0]) is HutSchema
    for hut in huts:
        assert hut.country_code == "nz"
        assert hut.capacity.if_open is None  # campsites never map capacity


def test_doc_nz_campsite_convert_dict_online(
    sources: list[DocNzCampsiteHutSource], service: DocNzCampsiteService
) -> None:
    """Convert by a dict."""
    for s in sources:
        hut = service.convert(s.model_dump(by_alias=True))
        assert type(hut) is HutSchema
        assert hut.name.en != ""
