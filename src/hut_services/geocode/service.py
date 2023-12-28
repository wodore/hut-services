#!/usr/bin/env python
# from functools import lru_cache
import logging
import typing as t

import httpx

# from typing import Any, Literal, Mapping
from hut_services import BaseService, file_cache
from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo.geo import LocationEleSchema, LocationSchema
from hut_services.geocode.schema import GeocodeHut0Convert, GeocodeHutSchema, GeocodeHutSource

# from hut_services.core.schema.geo import BBox

if __name__ == "__main__":  # only for testing
    from icecream import ic  # type: ignore[import-untyped] # noqa: F401, RUF100 , PGH003
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


@file_cache(ignore=["client"], expire_in_seconds=60 * 24 * 7 * 4)  # one month
def _get_location_by_name(
    name: str,
    request_url: str,
    client: httpx.Client | None = None,
    countries: t.Sequence[str] = ["ch", "de", "fr", "it", "at"],
    languages: t.Sequence[str] | None = None,
) -> t.Any:
    logger.debug(f"Get location for {name} from '{request_url}'.")
    if client is None:
        client = httpx.Client()
    country_codes = ",".join(countries)
    accept_lang = ",".join(languages) if languages else country_codes
    params: dict[str, str | int | bool] = {
        "amenity": "Neue Regensburger Huette",
        "format": "jsonv2",
        "limit": 1,
        "extratags": True,
        "countrycodes": country_codes,
        "accept-language": accept_lang,
    }
    return client.get(url=request_url, params=params).json()


@file_cache(ignore=["client"], expire_in_seconds=60 * 24 * 7 * 4 * 12)  # 12 months
def _get_elevations(
    locations: t.Sequence[LocationSchema | LocationEleSchema],
    request_url: str,
    client: httpx.Client | None = None,
) -> t.Any:
    logger.debug(f"Get elevation for {locations} from '{request_url}'.")
    if client is None:
        client = httpx.Client()
    params: dict[str, str | int | bool] = {
        "locations": "|".join([f"{location.lat},{location.lon}" for location in locations])
    }
    # Post does somehow not work
    # data = {"locations": [{"latitude": loc.lat, "longitude": loc.lon} for loc in locations]}
    # res = client.post(url=request_url, data=data, headers=headers)
    headers = {"Content-Type": "application/json"}
    res = client.get(url=request_url, params=params, headers=headers)
    return res.json().get("results", [])


class GeocodeService(BaseService[GeocodeHutSource]):
    """Service to get Information from
    [Nominatim](https://nominatim.openstreetmap.org).

    Note:
        This is not used to get huts, rather to get additional info (like location) from huts.
    """

    def __init__(self) -> None:
        super().__init__(support_bbox=True, support_limit=True, support_offset=True, support_convert=True)
        self.loc_request_url = "https://nominatim.openstreetmap.org/search"
        self.ele_request_url = "https://api.open-elevation.com/api/v1/lookup"
        self.httpx_client = httpx.Client()

    def get_location_by_name(self, name: str, client: httpx.Client | None = None) -> LocationEleSchema | None:
        """Get location (coordinates) from a name (uses 'https://nominatim.openstreetmap.org)."""
        client = client if client is not None else self.httpx_client
        res = _get_location_by_name(name=name, request_url=self.loc_request_url, client=client)
        if res:
            return GeocodeHutSchema(**res[0]).get_location()
        return None

    def get_elevations(
        self, locations: t.Sequence[LocationSchema | LocationEleSchema], client: httpx.Client | None = None
    ) -> list[LocationEleSchema]:
        """Get elevations from a list of locations (coordinates) (uses 'https://open-elevation.com)."""
        client = client if client is not None else self.httpx_client
        res = _get_elevations(locations=locations, request_url=self.ele_request_url, client=client)
        locs: list[LocationEleSchema] = []
        for i, loc in enumerate(locations):
            ele = res[i].get("elevation")
            locs.append(LocationEleSchema(lat=loc.lat, lon=loc.lon, ele=ele))
        return locs

    def get_elevation(
        self, location: LocationSchema | LocationEleSchema, client: httpx.Client | None = None
    ) -> LocationEleSchema:
        """Get elevation from a location (coordinates) (uses 'https://open-elevation.com)."""
        client = client if client is not None else self.httpx_client
        return self.get_elevations(locations=[location], client=client)[0]

    # NOT IMPLEMENTED:
    # def get_huts_from_source(
    #    self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict
    # ) -> list[GeocodeHutSource]:

    def convert(self, src: t.Mapping | t.Any) -> HutSchema:
        hut_src = (
            GeocodeHutSource(**src)
            if isinstance(src, t.Mapping)
            else GeocodeHutSource.model_validate(src, from_attributes=True)
        )
        if hut_src.version >= 0:
            if hut_src.source_data is None:
                err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} without 'source_data' not allowed."
                raise AttributeError(err_msg)
            return GeocodeHut0Convert(source=hut_src.source_data).get_hut()
        else:
            err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} not implemented."
            raise NotImplementedError(err_msg)


geocode_service = GeocodeService()

if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
    # qid = "Q42157530"
    # qid = "Q887175"  # Bluemlisalp
    # service = WikidataService()
    # entity = service.get_entity(qid)
    # rprint(entity.get_photos())
    limit = 5
    service = GeocodeService()
    loc = service.get_location_by_name("Allmagelerhuette")
    rprint(loc)
    if loc:
        eles = service.get_elevations([loc])
        rprint(eles)

    ## service.get_wikidata_photos = wikidata_photos
    # huts = service.get_huts_from_source(limit=limit)
    # for h in huts:
    #    # rprint(h)
    #    hut = service.convert(h.model_dump(by_alias=True))
    #    rprint(hut.name.i18n)
    #    # rprint(hut.extras.get("wikidata"))
    #    rprint(hut.photos)
