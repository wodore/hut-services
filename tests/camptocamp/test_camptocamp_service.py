import pytest

from hut_services.camptocamp import CamptocampService
from hut_services.camptocamp.schema import CamptocampHutSource
from hut_services.core.schema import HutSchema

HUT_LIMIT: int = 2


@pytest.fixture(scope="module")
def service() -> CamptocampService:
    return CamptocampService()


@pytest.fixture(scope="module")
def hut_sources(service: CamptocampService) -> list[CamptocampHutSource]:
    huts = service.get_huts_from_source(limit=HUT_LIMIT, fetch_details=False)
    if not huts:
        pytest.skip("Camptocamp API not usable from this environment, skipping")
    return huts


@pytest.fixture(scope="module")
def huts(service: CamptocampService) -> list[HutSchema]:
    hut_sources_ = service.get_huts_from_source(limit=HUT_LIMIT, fetch_details=False)
    if not hut_sources_:
        pytest.skip("Camptocamp API not usable from this environment, skipping")
    return [service.convert(h, include_photos=False) for h in hut_sources_]


def test_camptocamp_service_source_online(hut_sources: list[CamptocampHutSource]) -> None:
    """Get huts from camptocamp.org."""
    assert len(hut_sources) == HUT_LIMIT
    for h in hut_sources:
        print(h.show(source_name=False))
        assert type(h) is CamptocampHutSource
        assert h.source_name == "camptocamp"
        assert h.source_id
        assert h.name


def test_camptocamp_service_hut_online(huts: list[HutSchema]) -> None:
    """Tests conversion to HutSchema as well."""
    assert len(huts) == HUT_LIMIT
    for h in huts:
        assert type(h) is HutSchema
        assert h.name.i18n
        assert h.url
        assert h.source is not None
        assert h.source.name == "camptocamp"


def test_camptocamp_service_convert_dict_online(
    hut_sources: list[CamptocampHutSource], service: CamptocampService
) -> None:
    """Convert by a dict."""
    for h in hut_sources:
        h_dict = h.model_dump(by_alias=True)
        converted = service.convert(h_dict, include_photos=False)
        assert type(converted) is HutSchema


def test_camptocamp_service_photos_online(service: CamptocampService) -> None:
    """Photos can be fetched on request, and are skipped when not requested."""
    hut_sources_ = service.get_huts_from_source(limit=1, fetch_details=True)
    if not hut_sources_:
        pytest.skip("Camptocamp API not usable from this environment, skipping")
    hut = service.convert(hut_sources_[0], include_photos=True)
    assert type(hut) is HutSchema
    if hut_sources_[0].source_data is not None and hut_sources_[0].source_data.get_image_ids():
        assert len(hut.photos) > 0
    for p in hut.photos:
        assert p.raw_url
        assert p.url
        assert p.width > 0
        assert p.height > 0
        assert p.licenses
        assert p.source is not None
    hut_no_photos = service.convert(hut_sources_[0], include_photos=False)
    assert hut_no_photos.photos == []


def test_camptocamp_service_location(hut_sources: list[CamptocampHutSource]) -> None:
    """Locations from the source data are valid WGS84 coordinates."""
    for h in hut_sources:
        assert h.location is not None
        assert -90 <= h.location.lat <= 90
        assert -180 <= h.location.lon <= 180
