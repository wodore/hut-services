#!/usr/bin/env python
# from functools import lru_cache
from typing import List

import click
import overpy

from hut_services.core.schema.geo import BBox
from hut_services.osm.schema import HutOsm, HutOsmSource

if __name__ == "__main__":  # only for testing
    from rich import print  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


class OsmService:
    def __init__(self, request_url: str = "https://overpass.osm.ch/api/", log=False):
        self.request_url = request_url
        self._log = log
        self._cache = {}

    def _echo(self, *args, **kwargs):
        if self._log:
            click.secho(*args, **kwargs)

    # @lru_cache(10)
    def get_huts_from_source(
        self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs
    ) -> List[HutOsmSource]:
        """Get all huts from openstreet map."""
        api = overpy.Overpass(url=self.request_url)
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
        area = ",".join(
            [str(b) for b in bbox]
        )  # f"{lon_start},{lat_start},{lon_start+lon_range},{lat_start+lat_range}"
        self._echo(f"  .. get osm data from {self.request_url} with query:", dim=True)
        self._echo("     --------------------------", dim=True)
        query = f"""
                [out:json];
                (
                nw["tourism"="alpine_hut"]["name"]({area});
                nw["tourism"="wilderness_hut"]["name"]({area});
                );
                out qt center {limit};
            """
        self._echo(query, dim=True)
        self._echo("     --------------------------", dim=True, nl=False)
        try:
            result = api.query(query)
        except overpy.exception.OverpassGatewayTimeout as e:
            self._echo(" ... failed", fg="red")
            self._echo(e, dim=True)
            return []
        huts = []
        for key, res in {"node": result.nodes, "way": result.ways}.items():
            for h in res:
                osm_hut = HutOsm.model_validate(h, from_attributes=True)
                osm_hut.osm_type = key  # type: ignore  # noqa: PGH003
                hut = HutOsmSource(
                    name=osm_hut.get_name(),
                    source_id=osm_hut.get_id(),
                    location=osm_hut.get_point(),
                    source_data=osm_hut,
                )
                huts.append(hut)
                # huts.append(h)
        self._echo("  ... done", fg="green")
        return huts

    # @lru_cache(10)
    # def get_hut_list(self, limit: int = 5000, lang: str = "de") -> List[Hut]:
    #    huts = []
    #    osm_huts = self.get_osm_hut_list(limit=limit, lang=lang)
    #    huts = [h.get_hut() for h in osm_huts]
    #    return huts


if __name__ == "__main__":

    def main():
        limit = 30
        osm_service = OsmService(log=True)
        huts = osm_service.get_huts_from_source(limit)
        for h in huts:
            print(h.name)

    main()
