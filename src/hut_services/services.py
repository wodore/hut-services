from hut_services import BaseService, HutSourceSchema

from .camptocamp.service import CamptocampService
from .doc_nz.service import DocNzService
from .osm.service import OsmService
from .refuges_info.service import RefugesInfoService
from .wikidata.service import WikidataService

SERVICES: dict[str, BaseService[HutSourceSchema]] = {
    "camptocamp": CamptocampService(),
    "doc_nz": DocNzService(),
    "osm": OsmService(),
    "refuges": RefugesInfoService(),
    "wikidata": WikidataService(),
}
