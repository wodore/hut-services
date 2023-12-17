from hut_services.core.schema import HutSchema
from hut_services.refuges_info import RefugesInfoService
from hut_services.refuges_info.schema import RefugesInfoHutSource


def test_refuges_info_service_source_online() -> None:
    """Get huts from opemstreemap.org"""
    limit = 2
    osm_service = RefugesInfoService()
    huts = osm_service.get_huts_from_source(limit=limit)
    assert len(huts) == 2
    for h in huts:
        # rprint(h)
        print(h.show(source_name=False))
        assert type(h) == RefugesInfoHutSource


def test_refuges_info_service_hut_online() -> None:
    """Tests conversion to HutSchema as well."""
    limit = 2
    osm_service = RefugesInfoService()
    huts = osm_service.get_huts(limit=limit)
    assert len(huts) == 2
    assert type(huts[0]) == HutSchema
