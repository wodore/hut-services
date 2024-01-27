#!/usr/bin/env python
# from functools import lru_cache
import logging
import typing as t
import urllib.parse

# from typing import Any, Literal, Mapping
from wikidata.client import Client
from wikidata.entity import EntityId

from hut_services import BaseService, PhotoSchema, file_cache
from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox
from hut_services.osm.service import OsmService
from hut_services.wikidata.schema import WikidataHut0Convert, WikidataHutSchema, WikidataHutSource, WikidataProperties

if __name__ == "__main__":  # only for testing
    from icecream import ic  # type: ignore[import-untyped] # noqa: F401, RUF100 , PGH003
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


@file_cache(ignore=["client"])
def _get_photos(client: Client, qid: EntityId, thumb_width: int | None = 400) -> list[PhotoSchema]:
    image_prop = client.get(EntityId("P18"))  # image
    entity = client.get(qid, load=True)
    wikidata_url = f"https://www.wikidata.org/wiki/{qid.upper()}"
    if image_prop not in entity:
        logger.debug(f"No wikidata image for: '{wikidata_url}'")
        return []
    image = entity[image_prop]
    logger.info(f"Got wikidata image entity: '{image.title}'")  # type: ignore[attr-defined]
    title = urllib.parse.quote(image.title)  # type: ignore[attr-defined]
    link = f"https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/{title}"
    if thumb_width:
        thumb = f"https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/{title}&width={thumb_width}"
    else:
        thumb = ""
    # attribution = f'[{image.title.replace("File:","")}]({image.attributes.get("canonicalurl")}), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode)'  # type: ignore[attr-defined]
    attribution = f'<a href="{image.attributes.get("canonicalurl")}" target="_blank">{image.title.replace("File:","")}</a>, <a href="https://creativecommons.org/licenses/by-sa/4.0/legalcode" target="_blank">CC BY-SA 4.0</a>'  # type: ignore[attr-defined]
    # attribution = "CC BY-SA 4.0"  # type: ignore[attr-defined]
    comment = f"From {wikidata_url}"
    return [PhotoSchema(url=link, thumb=thumb, attribution=attribution, comment=comment, caption=None)]


@file_cache(ignore=["client"])
def _get_attributes(client: Client, qid: EntityId) -> dict[str, t.Any]:
    entity = client.get(qid, load=True)
    return dict(entity.attributes.items())


class WikidataEntity:
    def __init__(self, qid: EntityId, client: Client | None):
        self.client = Client() if client is None else client
        self.qid = qid

    def get_photos(self, thumb_width: int | None = 400) -> list[PhotoSchema]:
        """Get a list of photos from wikidata."""
        photos = _get_photos(client=self.client, qid=self.qid, thumb_width=thumb_width)
        assert all(isinstance(p, PhotoSchema) for p in photos), "Wrong type, not a list of 'PhotoSchema'"  # noqa: S101
        return t.cast(list[PhotoSchema], photos)

    def get_attributes(
        self,
    ) -> dict[str, t.Any]:
        """Get a list of photos from wikidata."""
        attributes = _get_attributes(client=self.client, qid=self.qid)
        # assert all(
        #    isinstance(p, dict[str, t.Any]) for p in attributes
        # ), "Wrong type, not a list of 'PhotoSchema'"
        return t.cast(dict[str, t.Any], attributes)


class WikidataService(BaseService[WikidataHutSource]):
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

    def get_huts_from_source(
        self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict
    ) -> list[WikidataHutSource]:
        osm_service = OsmService()
        osm_huts = osm_service.get_huts_from_source(bbox=bbox, limit=limit * 10, offset=offset, **kwargs)
        huts = []
        for oh in osm_huts:
            tags = oh.source_data.tags if oh.source_data else None
            if tags is None:
                continue
            qid = tags.wikidata
            if not qid:
                continue
            logger.info(f" Wikidata entry {qid:<15} ({oh.name})")
            wikidata = wikidata_service.get_entity(qid)
            lon, lat = oh.location.lon_lat if oh.location else (None, None)
            wikidata_hut = WikidataHutSchema(
                id=qid,
                name=oh.name,
                lat=lat,
                lon=lon,
                attributes=wikidata.get_attributes(),
                photos=wikidata.get_photos(),
            )
            hut = WikidataHutSource(
                name=wikidata_hut.get_name(),
                source_id=wikidata_hut.get_id(),
                location=wikidata_hut.get_location(),
                source_data=wikidata_hut,
                source_properties=WikidataProperties(),
            )
            huts.append(hut)
            if len(huts) >= limit:
                break
        return huts

    def convert(self, src: t.Mapping | t.Any) -> HutSchema:
        hut_src = (
            WikidataHutSource(**src)
            if isinstance(src, t.Mapping)
            else WikidataHutSource.model_validate(src, from_attributes=True)
        )
        if hut_src.version >= 0:
            if hut_src.source_data is None:
                err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} without 'source_data' not allowed."
                raise AttributeError(err_msg)
            return WikidataHut0Convert(source=hut_src.source_data).get_hut()
        else:
            err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} not implemented."
            raise NotImplementedError(err_msg)


wikidata_service = WikidataService()

if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
    # qid = "Q42157530"
    # qid = "Q887175"  # Bluemlisalp
    # service = WikidataService()
    # entity = service.get_entity(qid)
    # rprint(entity.get_photos())
    limit = 5
    service = WikidataService()
    # service.get_wikidata_photos = wikidata_photos
    huts = service.get_huts_from_source(limit=limit)
    for h in huts:
        # rprint(h)
        hut = service.convert(h.model_dump(by_alias=True))
        rprint(hut.name.i18n)
        # rprint(hut.extras.get("wikidata"))
        rprint(hut.photos)
