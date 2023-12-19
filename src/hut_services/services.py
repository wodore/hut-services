from hut_services import BaseService, HutSourceSchema

from .osm.service import OsmService
from .refuges_info.service import RefugesInfoService

SERVICES: dict[str, BaseService[HutSourceSchema]] = {
    "osm": OsmService(),
    "refuges": RefugesInfoService(),
}
