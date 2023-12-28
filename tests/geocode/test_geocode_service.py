import pytest
from hut_services.core.schema.geo import LocationSchema
from hut_services.geocode.service import GeocodeService, geocode_service


def test_geocode_get_location() -> None:
    service = GeocodeService()
    name = "Almagellerhuette"
    coord = service.get_location_by_name(name)
    assert coord, "Nothing returned"
    assert pytest.approx(coord.lat) == 46.1076
    assert pytest.approx(coord.lon) == 8.007716


def test_geocode_get_elevations() -> None:
    service = geocode_service
    location = LocationSchema(lat=47.0, lon=11.1)
    location2 = LocationSchema(lat=46.0, lon=10.1)
    locations = [location, location2]
    eles = service.get_elevations(locations)
    assert eles, "Nothing returned"
    assert len(eles) == 2
    assert pytest.approx(eles[0].ele) == 2947
    assert pytest.approx(eles[1].ele) == 1087
    ele = service.get_elevation(location)
    assert pytest.approx(ele.ele) == eles[0].ele
