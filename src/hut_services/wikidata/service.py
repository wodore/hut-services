#!/usr/bin/env python
# from functools import lru_cache
import logging
import urllib.parse

# from typing import Any, Literal, Mapping
from wikidata.client import Client
from wikidata.entity import EntityId

from hut_services import BaseHutSourceSchema, BaseService, PhotoSchema

if __name__ == "__main__":  # only for testing
    from icecream import ic  # type: ignore[import-untyped] # noqa: F401, RUF100 , PGH003
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


class WikidataEntity:
    def __init__(self, qid: EntityId, client: Client | None):
        self.client = Client() if client is None else client
        self.qid = qid
        self.entity = self.client.get(qid, load=True)

    def get_photos(self, thumb_width: int | None = 400) -> list[PhotoSchema]:
        image_prop = self.client.get(EntityId("P18"))  # image
        if image_prop not in self.entity:
            return []
        image = self.entity[image_prop]
        title = urllib.parse.quote(image.title)  # type: ignore[attr-defined]
        link = f"https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/{title}"
        if thumb_width:
            thumb = f"https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/{title}&width={thumb_width}"
        else:
            thumb = None
        attribution = f'[{image.title.replace("File:","")}]({image.attributes.get("canonicalurl")}), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode)'  # type: ignore[attr-defined]
        comment = f"From https://www.wikidata.org/wiki/{self.qid.upper()}"
        return [PhotoSchema(url=link, thumb=thumb, attribution=attribution, comment=comment)]  # pyright: ignore  # noqa: PGH003


class WikidataService(BaseService[BaseHutSourceSchema]):
    """Service to get Information from
    [Wikidata](https://www.wikidata.org/)
    with a [Python Wikidata](https://pypi.org/project/Wikidata/) client.

    Note:
        It is not (yet) possible to get huts and convert them.
    """

    def __init__(self, request_url: str = "https://www.wikidata.org/"):
        super().__init__(support_bbox=True, support_limit=True, support_offset=True, support_convert=True)
        self.request_url = request_url
        self.wikidata_client = Client(base_url=request_url)

    def get_entity(self, qid: str) -> WikidataEntity:
        qid_e = EntityId(qid)
        return WikidataEntity(qid_e, self.wikidata_client)

    # NOT IMPLEMENTED:

    ## @lru_cache(10)
    # def get_huts_from_source(
    #    self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict
    # ) -> list[OsmHutSource]:

    # def convert(self, src: Mapping | Any) -> HutSchema:


wikidata_service = WikidataService()

if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
    qid = "Q42157530"
    qid = "Q887175"  # Bluemlisalp
    service = WikidataService()
    entity = service.get_entity(qid)
    rprint(entity.get_photos())
