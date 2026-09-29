from hut_services import BaseService, HutSourceSchema

from .camptocamp.service import CamptocampService
from .osm.service import OsmService
from .refuges_info.service import RefugesInfoService
from .wikidata.service import WikidataService

SERVICES: dict[str, BaseService[HutSourceSchema]] = {
    "camptocamp": CamptocampService(),
    "osm": OsmService(),
    "refuges": RefugesInfoService(),
    "wikidata": WikidataService(),
}
