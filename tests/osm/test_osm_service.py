from hut_services.osm import OsmService


def test_osm_service_online():
    limit = 2
    osm_service = OsmService(log=True)
    huts = osm_service.get_huts_from_source(limit=limit)
    assert len(huts) == 2
    for h in huts:
        # rprint(h)
        print(h.show(source_name=False))
