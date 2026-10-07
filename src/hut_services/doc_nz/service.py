"""Service to get huts from New Zealand's Department of Conservation (DOC).

Base data: the official "DOC Huts" open-data layer (~1'400 huts and bivvies,
ArcGIS FeatureServer, CC-BY 4.0, no authentication) with coordinates, the
`bookable` flag, facilities and hut-page links.

Optional enrichment: the official DOC API v2 (free key from
<https://api.doc.govt.nz>, sent as `x-api-key` header) adds bunk counts,
hut categories, introductions and a bulk alerts endpoint. Used
automatically whenever a key is configured (`api_key` argument or
`HUT_SRV_DOC_NZ_API_KEY` environment variable); opt out with `enrich=False`.
"""

import logging
import os
import time
import typing as t

import httpx
from pydantic import ValidationError

from hut_services.core.cache import file_cache
from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox
from hut_services.core.service import BaseService

from .schema import (
    DocNzDetailSchema,
    DocNzHut0Convert,
    DocNzHutAlerts,
    DocNzHutSchema,
    DocNzHutSource,
    DocNzProperties,
)

logger = logging.getLogger(__name__)

DOC_NZ_FEATURESERVER_URL: str = (
    "https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/DOC_Huts/FeatureServer/0/query"
)
DOC_NZ_API_URL: str = "https://api.doc.govt.nz/v2"
DOC_NZ_PAGE_SIZE: int = 2000  # max records per FeatureServer request


@file_cache()
def doc_nz_request(
    request_url: str = DOC_NZ_FEATURESERVER_URL,
    bbox: BBox | None = None,
    limit: int = 0,
    offset: int = 0,
) -> list[DocNzHutSchema]:
    """Query the DOC NZ huts ArcGIS FeatureServer (WGS84, file-cached).

    Args:
        request_url: FeatureServer query endpoint.
        bbox: Optional boundary box (WGS84).
        limit: Maximum number of huts, `0` for all.
        offset: Query offset.

    Returns:
        Huts from the layer.
    """
    result_offset = max(offset, 0)
    result_count = limit if limit and limit > 0 else DOC_NZ_PAGE_SIZE
    features: list[dict[str, t.Any]] = []
    while True:
        params: dict[str, t.Any] = {
            "where": "1=1",
            "outFields": "*",
            "outSR": "4326",
            "f": "json",
            "resultOffset": result_offset,
            "resultRecordCount": result_count,
        }
        if bbox is not None:
            params.update(
                {
                    "geometry": ",".join(str(b) for b in bbox),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                }
            )
        r = httpx.get(request_url, params=params, timeout=30)
        logger.debug(f"request url: {r.url}")
        r.raise_for_status()
        batch: list[dict[str, t.Any]] = r.json().get("features", [])
        features.extend(batch)
        if not batch or len(batch) < result_count:
            break  # last page reached
        result_offset += len(batch)
        if limit and limit > 0:
            break  # single limited request is enough
    huts: list[DocNzHutSchema] = []
    for feature in features:
        attributes: dict[str, t.Any] = dict(feature.get("attributes", {}))
        geometry: dict[str, t.Any] = feature.get("geometry") or {}
        # with `outSR=4326` the point geometry is {"x": <lon>, "y": <lat>}
        attributes["lon"] = geometry.get("x")
        attributes["lat"] = geometry.get("y")
        try:
            huts.append(DocNzHutSchema.model_validate(attributes))
        except ValidationError as e:
            name = attributes.get("name", "?")
            logger.warning(f"cannot parse DOC NZ hut '{name}': {e.error_count()} error(s): {e.errors()[0]['msg']}")
    logger.info(f"successfully got {len(huts)} huts from the DOC NZ layer")
    return huts


@file_cache(ignore=["api_key"])
def doc_nz_detail_request(api_url: str, asset_id: int, api_key: str, _delay: float = 0.3) -> dict[str, t.Any] | None:
    """Get hut detail from the DOC API v2 `/huts/{id}/detail` (file-cached).

    Returns `None` if the hut is not found or the key has no access.
    """
    r = httpx.get(
        f"{api_url}/huts/{asset_id}/detail",
        params={"coordinates": "wgs84"},
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=15,
    )
    time.sleep(_delay)
    if r.status_code in (403, 404):
        logger.info(f"DOC API detail for hut {asset_id}: HTTP {r.status_code}")
        return None
    r.raise_for_status()
    return t.cast("dict[str, t.Any]", r.json())


@file_cache(ignore=["api_key"])
def doc_nz_alerts_request(api_url: str, api_key: str) -> list[DocNzHutAlerts]:
    """Get alerts for all huts from the DOC API v2 `/huts/alerts` (file-cached)."""
    r = httpx.get(
        f"{api_url}/huts/alerts",
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = t.cast("list[dict[str, t.Any]]", r.json())
    return [DocNzHutAlerts.model_validate(a) for a in data]


class DocNzService(BaseService[DocNzHutSource]):
    """Service to get huts from New Zealand's
    [Department of Conservation](https://www.doc.govt.nz)
    ([DOC Huts open data](https://doc-deptconservation.opendata.arcgis.com/maps/doc-huts),
    optionally enriched with the official [DOC API](https://api.doc.govt.nz)).

    Note:
        The methods are described in [`BaseService`][hut_services.BaseService].

    Examples:
        ```python
        from hut_services.doc_nz import DocNzService
        service = DocNzService()
        huts = service.get_huts(limit=20)  # base layer, no API key needed
        ```

        With detail enrichment (bunks, category, introduction) — done
        automatically when a key is configured, free key from
        <https://api.doc.govt.nz>:
        ```python
        service = DocNzService(api_key="...")
        huts = service.get_huts(limit=20)  # enriched, one cached request per hut
        ```
    """

    def __init__(
        self,
        request_url: str = DOC_NZ_FEATURESERVER_URL,
        api_url: str = DOC_NZ_API_URL,
        api_key: str | None = None,
    ) -> None:
        super().__init__(support_bbox=True, support_limit=True, support_offset=True, support_convert=True)
        self.request_url = request_url
        self.api_url = api_url
        self.api_key = api_key if api_key is not None else os.environ.get("HUT_SRV_DOC_NZ_API_KEY")

    def get_huts_from_source(
        self,
        bbox: BBox | None = None,
        limit: int = 1,
        offset: int = 0,
        enrich: bool | None = None,
        **kwargs: t.Any,
    ) -> list[DocNzHutSource]:
        """Get huts from the DOC NZ open-data layer.

        Args:
            bbox: Boundary box.
            limit: Limit (how many entries to retrieve), `0` for all.
            offset: Offset of the request.
            enrich: Fetch detail (bunks, category, introduction, status) from
                the official DOC API v2 for every hut — one request per hut
                (file-cached). `None` (default): enrich automatically when an
                API key is configured (`api_key` argument or `HUT_SRV_DOC_NZ_API_KEY`
                environment variable); `True`: require a key (raises without);
                `False`: never enrich.

        Returns:
            Huts from source.
        """
        logger.info(f"get DOC NZ huts from {self.request_url}")
        src_huts = doc_nz_request(request_url=self.request_url, bbox=bbox, limit=limit, offset=offset)
        if enrich is None:
            enrich = self.api_key is not None
        if enrich:
            if not self.api_key:
                msg = "DOC API key required for enrichment: pass `api_key` or set `HUT_SRV_DOC_NZ_API_KEY`."
                raise ValueError(msg)
            src_huts = [self._enrich_hut(hut) for hut in src_huts]
        huts: list[DocNzHutSource] = []
        for hut in src_huts:
            huts.append(
                DocNzHutSource(
                    name=hut.get_name(),
                    source_data=hut,
                    source_id=hut.get_id(),
                    location=hut.get_location(),
                    source_properties=DocNzProperties(
                        bookable=hut.bookable,
                        region=hut.region,
                        place=hut.place,
                        hut_category=hut.hut_category,
                    ),
                )
            )
        return huts

    def _enrich_hut(self, hut: DocNzHutSchema) -> DocNzHutSchema:
        """Merge DOC API v2 detail fields into a layer hut (best effort)."""
        if not self.api_key:
            return hut
        raw = doc_nz_detail_request(self.api_url, hut.asset_id, self.api_key)
        if raw is None:
            return hut
        try:
            detail = DocNzDetailSchema.model_validate(raw)
        except ValidationError as e:
            logger.warning(f"cannot parse DOC API detail for hut {hut.asset_id}: {e.errors()[0]['msg']}")
            return hut
        return hut.model_copy(update=detail.model_dump())

    def get_alerts(self) -> list[DocNzHutAlerts]:
        """Get current alerts for all huts from the DOC API v2 (needs an API key).

        Returns:
            List of alerts per hut (`assetId`, hut `name`, `alerts`).
        """
        if not self.api_key:
            msg = "DOC API key required for alerts: pass `api_key` or set `HUT_SRV_DOC_NZ_API_KEY`."
            raise ValueError(msg)
        alerts = doc_nz_alerts_request(self.api_url, self.api_key)
        return t.cast("list[DocNzHutAlerts]", alerts)

    def convert(self, src: t.Mapping | t.Any, include_photos: bool = True) -> HutSchema:
        hut_src = (
            DocNzHutSource(**src)
            if isinstance(src, t.Mapping)
            else DocNzHutSource.model_validate(src, from_attributes=True)
        )
        if hut_src.version >= 0:
            if hut_src.source_data is None:
                err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} without 'source_data' not allowed."
                raise AttributeError(err_msg)
            return DocNzHut0Convert(include_photos=include_photos, source_data=hut_src.source_data).get_hut()
        else:
            err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} not implemented."
            raise NotImplementedError(err_msg)


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(format="%(levelname)s:%(message)s", level=_logging.INFO)
    from rich import print as rprint
    from rich.traceback import install

    install(show_locals=False)

    doc_nz_service = DocNzService()
    huts = doc_nz_service.get_huts_from_source(limit=5)
    for h in huts:
        rprint("====================")
        rprint(h)
        hut = doc_nz_service.convert(h.model_dump(by_alias=True))
        rprint(hut.name.i18n)
        rprint(hut.capacity)
        rprint(hut.url)
        rprint(hut.extras)
