from rich import print as rprint

from hut_services import OsmService

osm_service = OsmService()
osm_service.get_wikidata_photos = True  # include photos
huts = osm_service.get_huts_from_source(limit=5)  # get the first 10 entries
for h in huts:
    hut = osm_service.convert(h.model_dump(by_alias=True))
    rprint(hut.name.i18n)
    rprint(hut.url) if hut.url else None
    if hut.photos:
        rprint(hut.photos)
