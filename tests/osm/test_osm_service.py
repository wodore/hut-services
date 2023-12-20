import pytest
from hut_services.core.schema import HutSchema
from hut_services.osm import OsmService
from hut_services.osm.schema import OsmHutSource

HUT_LIMIT: int = 2


@pytest.fixture(scope="module")
def service() -> OsmService:
    return OsmService()


@pytest.fixture(scope="module")
def hut_sources(service) -> list[OsmHutSource]:
    return service.get_huts_from_source(limit=HUT_LIMIT)


@pytest.fixture(scope="module")
def huts(service) -> list[HutSchema]:
    return service.get_huts(limit=HUT_LIMIT)


def test_osm_service_source_online(hut_sources: list[OsmHutSource]) -> None:
    """Get huts from opemstreemap.org"""
    assert len(hut_sources) == HUT_LIMIT
    for h in hut_sources:
        # rprint(h)
        print(h.show(source_name=False))
        assert type(h) == OsmHutSource


def test_osm_service_hut_online(huts: list[HutSchema]) -> None:
    """Tests conversion to HutSchema as well."""
    assert len(huts) == 2
    assert type(huts[0]) == HutSchema


def test_osm_service_convert_dict_online(hut_sources: list[OsmHutSource], service: OsmService) -> None:
    """Convert by a dict"""
    for h in hut_sources:
        h_dict = h.model_dump(by_alias=True)
        # add a field
        h_dict["psuedo"] = "No needed"
        service.convert(h_dict)


def test_osm_service_convert_obj_online(hut_sources: list[OsmHutSource], service: OsmService) -> None:
    """Convert by a random class with missing location"""

    class MySource:
        def __init__(self, data: dict, name: str):
            self.source_data = data
            self.source_id = 10
            self.name = name
            self.random = 200

    for h in hut_sources:
        h_obj = MySource(data=h.source_data.model_dump(by_alias=True) if h.source_data else {}, name="MyName")
        service.convert(h_obj)


def test_osm_service_convert_obj2_online(hut_sources: list[OsmHutSource], service: OsmService) -> None:
    """Convert by a random class with location (x,y,z)"""

    class MySource:
        def __init__(self, data: dict, name: str):
            self.source_data = data
            self.source_id = 10
            self.location: dict = {"x": 45, "y": 10, "z": 2000}
            self.name = name
            self.random = 200

    for h in hut_sources:
        h_obj = MySource(data=h.source_data.model_dump(by_alias=True) if h.source_data else {}, name="MyName")
        h_c = service.convert(h_obj)
        assert h_c.name.i18n == h.name
