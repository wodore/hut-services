from hut_services.core.schema import HutSchema
from hut_services.osm import OsmService
from hut_services.osm.schema import OsmHutSource


def test_osm_service_source_online() -> None:
    """Get huts from opemstreemap.org"""
    limit = 2
    osm_service = OsmService()
    huts = osm_service.get_huts_from_source(limit=limit)
    assert len(huts) == 2
    for h in huts:
        # rprint(h)
        print(h.show(source_name=False))
        assert type(h) == OsmHutSource


def test_osm_service_hut_online() -> None:
    """Tests conversion to HutSchema as well."""
    limit = 2
    osm_service = OsmService()
    huts = osm_service.get_huts(limit=limit)
    assert len(huts) == 2
    assert type(huts[0]) == HutSchema
