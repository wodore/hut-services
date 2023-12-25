#!/usr/bin/env python
# from functools import lru_cache
import logging
import textwrap
import typing as t

import overpy  # type: ignore[import-untyped]

from hut_services.core.cache import file_cache
from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox
from hut_services.core.service import BaseService
from hut_services.osm.schema import OsmHut0Convert, OsmHutSchema, OsmHutSource, OsmProperties

if __name__ == "__main__":  # only for testing
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


@file_cache(ignore=["api"])
def _get_huts_from_source(
    api: t.Any, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict
) -> list[OsmHutSource]:
    if bbox is None:
        # fetch all ways and nodes
        # SWISS
        lon = [45.7553, 47.6203]
        lat = [5.7127, 10.5796]
        bounder = 100.0
        lon_diff = lon[1] - lon[0]
        lat_diff = lat[1] - lat[0]
        lon_range = lon_diff / bounder * limit + lon_diff / bounder * 2 * offset
        lon_range = lon_diff if lon_range > lon_diff else lon_range
        lat_range = lat_diff / bounder * limit + lat_diff / bounder * 2 * offset
        lat_range = lat_diff if lat_range > lat_diff else lat_range
        lon_start = lon[0] + (lon_diff - lon_range) / 2
        lat_start = lat[0] + (lat_diff - lat_range) / 2
        bbox = (lon_start, lat_start, lon_start + lon_range, lat_start + lat_range)
    area = ",".join([str(b) for b in bbox])  # f"{lon_start},{lat_start},{lon_start+lon_range},{lat_start+lat_range}"
    logger.info(f"get osm data from {api.url} with bbox: ({area})")
    query = f"""
            [out:json];
            (
            nw["tourism"="alpine_hut"]["name"]({area});
            nw["tourism"="wilderness_hut"]["name"]({area});
            );
            out qt center {limit};
        """
    logger.debug(f"query:\n{'-'*20}\n{textwrap.dedent(query).strip()}\n{'-'*20}")
    try:
        result = api.query(query)
    except overpy.exception.OverpassGatewayTimeout as e:
        logger.warning("overpy execution failed")
        logger.debug(str(e))
        return []
    huts = []
    for _osm_type, res in {"node": result.nodes, "way": result.ways}.items():
        osm_type: t.Literal["node", "way", "area"] = _osm_type  # type: ignore  # noqa: PGH003 # ignore pyright and mypy str to literal assigment
        for h in res:
            osm_hut = OsmHutSchema.model_validate(h, from_attributes=True)
            osm_hut.osm_type = osm_type
            hut = OsmHutSource(
                name=osm_hut.get_name(),
                source_id=osm_hut.get_id(),
                location=osm_hut.get_location(),
                source_data=osm_hut,
                source_properties=OsmProperties(osm_type=osm_type),
            )
            huts.append(hut)
            # huts.append(h)
    logger.info(f"succesfully got {len(huts)} huts")
    return huts


class OsmService(BaseService[OsmHutSource]):
    """Service to get huts from
    [Open Street Map](https://www.openstreetmap.org/)
    with [overpass api](https://wiki.openstreetmap.org/wiki/Overpass_API).

    Note:
        The methods are descriebed in [`BaseService`][hut_services.BaseService].
    """

    def __init__(self, request_url: str = "https://overpass.osm.ch/api/", get_wikidata_photos: bool = True):
        super().__init__(support_bbox=True, support_limit=True, support_offset=True, support_convert=True)
        self.get_wikidata_photos = get_wikidata_photos
        self.request_url = request_url

    def get_huts_from_source(
        self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict
    ) -> list[OsmHutSource]:
        api = overpy.Overpass(url=self.request_url)
        huts = _get_huts_from_source(api=api, bbox=bbox, limit=limit, offset=offset, **kwargs)
        assert all(isinstance(p, OsmHutSource) for p in huts), "Wrong type, not a list of 'PhotoSchema'"  # noqa: S101
        return t.cast(list[OsmHutSource], huts)

    def convert(self, src: t.Mapping | t.Any) -> HutSchema:
        hut_src = (
            OsmHutSource(**src)
            if isinstance(src, t.Mapping)
            else OsmHutSource.model_validate(src, from_attributes=True)
        )
        if hut_src.version >= 0:
            if hut_src.source_data is None:
                err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} without 'source_data' not allowed."
                raise AttributeError(err_msg)
            return OsmHut0Convert(get_wikidata_photos=self.get_wikidata_photos, source=hut_src.source_data).get_hut()
        else:
            err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} not implemented."
            raise NotImplementedError(err_msg)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
    limit = 5000
    wikidata_photos = True
    osm_service = OsmService()
    osm_service.get_wikidata_photos = wikidata_photos
    huts = osm_service.get_huts_from_source(limit=limit)
    for h in huts:
        # rprint(h)
        hut = osm_service.convert(h.model_dump(by_alias=True))
        rprint(hut.name.i18n)
        rprint(hut.extras.get("wikidata"))
        rprint(hut.photos)
        # rprint(h.source_properties_schema)
        # rprint(h)
        # print(h.show(source_name=False))
