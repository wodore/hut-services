"""Service to get huts and campsites from New Zealand's Department of
Conservation (DOC).

Base data: the official "DOC Huts" (~1'400 huts and bivvies) and
"DOC Campsites" (~310 campsites) open-data layers (ArcGIS FeatureServer,
CC-BY 4.0, no authentication) with coordinates, `bookable` flags,
facilities and page links. `DocNzService` returns huts AND campsites
(`include_campsites=False` for huts only); `DocNzCampsiteService` is a
campsites-only convenience wrapper.

Optional enrichment: the official DOC API v2 (free key from
<https://api.doc.govt.nz>, sent as `x-api-key` header) adds bunk counts,
hut categories, introductions and bulk alerts endpoints. Used
automatically whenever a key is configured (`api_key` argument or
`HUT_SRV_DOC_NZ_API_KEY` environment variable); opt out with `enrich=False`.
Detail requests are sequential (no artificial delay) — network latency
keeps them far below the API's rate limit (100 req/s).
"""

import logging
import os
import re
import typing as t

import httpx
from pydantic import ValidationError

from hut_services.core.cache import file_cache
from hut_services.core.schema import HutSchema, PhotoSchema, SourceDataSchema
from hut_services.core.schema.geo import BBox
from hut_services.core.service import BaseService

from .images import get_hut_images
from .schema import (
    DocNzCampsite0Convert,
    DocNzCampsiteHutSource,
    DocNzCampsiteProperties,
    DocNzCampsiteSchema,
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
DOC_NZ_CAMPSITES_URL: str = (
    "https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/DOC_Campsites/FeatureServer/0/query"
)
DOC_NZ_API_URL: str = "https://api.doc.govt.nz/v2"
DOC_NZ_PAGE_SIZE: int = 2000  # max records per FeatureServer request


TLayerSchema = t.TypeVar("TLayerSchema", bound=SourceDataSchema)


@file_cache()
def doc_nz_layer_features(
    request_url: str,
    bbox: BBox | None = None,
    limit: int = 0,
    offset: int = 0,
) -> list[dict[str, t.Any]]:
    """Fetch raw features from a DOC NZ ArcGIS layer (WGS84, file-cached).

    Paginates, applies an optional `bbox` envelope filter and merges the
    point geometry (`outSR=4326`: `{"x": <lon>, "y": <lat>}`) into the
    attributes as `lat`/`lon` keys.
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
    merged: list[dict[str, t.Any]] = []
    for feature in features:
        attributes: dict[str, t.Any] = dict(feature.get("attributes", {}))
        geometry: dict[str, t.Any] = feature.get("geometry") or {}
        attributes["lon"] = geometry.get("x")
        attributes["lat"] = geometry.get("y")
        merged.append(attributes)
    return merged


def _parse_layer_features(
    features: list[dict[str, t.Any]], schema_cls: type[TLayerSchema], label: str
) -> list[TLayerSchema]:
    """Validate raw layer features into `schema_cls` (skips invalid ones with a warning)."""
    parsed: list[TLayerSchema] = []
    for attributes in features:
        try:
            parsed.append(schema_cls.model_validate(attributes))
        except ValidationError as e:
            name = attributes.get("name", "?")
            logger.warning(f"cannot parse DOC NZ {label} '{name}': {e.error_count()} error(s): {e.errors()[0]['msg']}")
    return parsed


def doc_nz_request(
    request_url: str = DOC_NZ_FEATURESERVER_URL,
    bbox: BBox | None = None,
    limit: int = 0,
    offset: int = 0,
) -> list[DocNzHutSchema]:
    """Query the DOC NZ huts ArcGIS FeatureServer (WGS84, file-cached)."""
    features = doc_nz_layer_features(request_url=request_url, bbox=bbox, limit=limit, offset=offset)
    huts = _parse_layer_features(features, DocNzHutSchema, "hut")
    logger.info(f"successfully got {len(huts)} huts from the DOC NZ layer")
    return huts


def doc_nz_campsite_request(
    request_url: str = DOC_NZ_CAMPSITES_URL,
    bbox: BBox | None = None,
    limit: int = 0,
    offset: int = 0,
) -> list[DocNzCampsiteSchema]:
    """Query the DOC NZ campsites ArcGIS FeatureServer (WGS84, file-cached)."""
    features = doc_nz_layer_features(request_url=request_url, bbox=bbox, limit=limit, offset=offset)
    campsites = _parse_layer_features(features, DocNzCampsiteSchema, "campsite")
    logger.info(f"successfully got {len(campsites)} campsites from the DOC NZ layer")
    return campsites


@file_cache(ignore=["api_key"])
def doc_nz_detail_request(api_url: str, asset_id: int, api_key: str, kind: str = "huts") -> dict[str, t.Any] | None:
    """Get asset detail from the DOC API v2 `/{kind}/{id}/detail` (file-cached).

    Sequential requests only — no artificial delay, network latency keeps
    them far below the API rate limit (100 req/s). Returns `None` if the
    asset is not found or the key has no access.
    """
    r = httpx.get(
        f"{api_url}/{kind}/{asset_id}/detail",
        params={"coordinates": "wgs84"},
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=15,
    )
    if r.status_code in (400, 403, 404):
        logger.info(f"DOC API detail for hut {asset_id}: HTTP {r.status_code}")
        return None
    r.raise_for_status()
    return t.cast("dict[str, t.Any]", r.json())


@file_cache(ignore=["api_key"])
def doc_nz_alerts_request(api_url: str, api_key: str, kind: str = "huts") -> list[DocNzHutAlerts]:
    """Get alerts for all assets from the DOC API v2 `/{kind}/alerts` (file-cached)."""
    r = httpx.get(
        f"{api_url}/{kind}/alerts",
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = t.cast("list[dict[str, t.Any]]", r.json())
    return [DocNzHutAlerts.model_validate(a) for a in data]


DocNzAnySource: t.TypeAlias = DocNzHutSource | DocNzCampsiteHutSource


@file_cache()
def _static_link_for(asset_id: int) -> str | None:
    """`staticLink` for an assetId, queried directly from the layers (huts first, then campsites)."""
    for query_url in (DOC_NZ_FEATURESERVER_URL, DOC_NZ_CAMPSITES_URL):
        try:
            r = httpx.get(
                query_url,
                params={"where": f"assetId={asset_id}", "outFields": "staticLink", "f": "json", "resultRecordCount": 1},
                timeout=20,
            )
            r.raise_for_status()
            features = r.json().get("features") or []
            if features:
                link = features[0].get("attributes", {}).get("staticLink")
                if link:
                    return str(link)
        except Exception as exc:
            logger.warning("doc_nz static link lookup for asset %s on %s failed: %r", asset_id, query_url, exc)
    return None


def _page_uuid(static_link: str | None) -> str | None:
    """uuid of a `/link/<uuid>.aspx` source link."""
    if static_link and (m := re.search(r"/link/([0-9a-f]{32})\.aspx", static_link)):
        return m.group(1)
    return None


def _enrich_hut(api_url: str, api_key: str, hut: DocNzHutSchema) -> DocNzHutSchema:
    """Merge DOC API v2 hut detail fields into a layer hut (best effort)."""
    raw = doc_nz_detail_request(api_url, hut.asset_id, api_key, kind="huts")
    if raw is None:
        return hut
    try:
        detail = DocNzDetailSchema.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"cannot parse DOC API detail for hut {hut.asset_id}: {e.errors()[0]['msg']}")
        return hut
    return hut.model_copy(update=detail.model_dump())


def _enrich_campsite(api_url: str, api_key: str, campsite: DocNzCampsiteSchema) -> DocNzCampsiteSchema:
    """Merge DOC API v2 campsite detail fields (status/introduction, best effort)."""
    raw = doc_nz_detail_request(api_url, campsite.asset_id, api_key, kind="campsites")
    if raw is None:
        return campsite
    update: dict[str, t.Any] = {}
    if raw.get("status") is not None:
        update["status"] = str(raw["status"])
    if raw.get("introduction"):
        update["introduction"] = str(raw["introduction"])
    return campsite.model_copy(update=update) if update else campsite


class DocNzService(BaseService[DocNzAnySource]):
    """Service to get huts AND campsites from New Zealand's
    [Department of Conservation](https://www.doc.govt.nz)
    ([DOC Huts](https://doc-deptconservation.opendata.arcgis.com/maps/doc-huts) and
    [DOC Campsites](https://doc-deptconservation.opendata.arcgis.com/maps/doc-campsites)
    open data, optionally enriched with the official [DOC API](https://api.doc.govt.nz)).

    Campsites are included by default (`include_campsites=False` for huts
    only); they convert to `camping`/`campgr` types without capacity.
    For campsites only use `DocNzCampsiteService`.

    Note:
        The methods are described in [`BaseService`][hut_services.BaseService].

    Examples:
        ```python
        from hut_services.doc_nz import DocNzService
        service = DocNzService()
        huts = service.get_huts(limit=20)  # huts + campsites, no API key needed
        ```

        With detail enrichment (bunks, category, introduction) — done
        automatically when a key is configured, free key from
        <https://api.doc.govt.nz>:
        ```python
        service = DocNzService(api_key="...")
        huts = service.get_huts(limit=20)  # enriched, one cached request per asset
        ```
    """

    def __init__(
        self,
        request_url: str = DOC_NZ_FEATURESERVER_URL,
        campsites_url: str = DOC_NZ_CAMPSITES_URL,
        api_url: str = DOC_NZ_API_URL,
        api_key: str | None = None,
    ) -> None:
        super().__init__(support_bbox=True, support_limit=True, support_offset=True, support_convert=True)
        self.request_url = request_url
        self.campsites_url = campsites_url
        self.api_url = api_url
        self.api_key = api_key if api_key is not None else os.environ.get("HUT_SRV_DOC_NZ_API_KEY")

    def get_huts_from_source(
        self,
        bbox: BBox | None = None,
        limit: int = 1,
        offset: int = 0,
        enrich: bool | None = None,
        include_campsites: bool = True,
        **kwargs: t.Any,
    ) -> list[DocNzAnySource]:
        """Get huts (and by default campsites) from the DOC NZ open-data layers.

        Args:
            bbox: Boundary box.
            limit: Limit per layer (how many entries to retrieve), `0` for all.
            offset: Offset of the requests.
            enrich: Fetch detail from the official DOC API v2 for every asset —
                one request per asset (file-cached). `None` (default): enrich
                automatically when an API key is configured (`api_key` argument
                or `HUT_SRV_DOC_NZ_API_KEY` environment variable); `True`:
                require a key (raises without); `False`: never enrich.
            include_campsites: Also return campsites (default). `limit`/`offset`
                apply to each layer separately.

        Returns:
            Huts (and campsites) from source.
        """
        if enrich is None:
            enrich = self.api_key is not None
        if enrich and not self.api_key:
            msg = "DOC API key required for enrichment: pass `api_key` or set `HUT_SRV_DOC_NZ_API_KEY`."
            raise ValueError(msg)
        logger.info(f"get DOC NZ huts from {self.request_url}")
        sources: list[DocNzAnySource] = []
        for hut in doc_nz_request(request_url=self.request_url, bbox=bbox, limit=limit, offset=offset):
            if enrich:
                hut = _enrich_hut(self.api_url, t.cast("str", self.api_key), hut)
            sources.append(
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
                        page_uuid=_page_uuid(hut.static_link),
                    ),
                )
            )
        if include_campsites:
            logger.info(f"get DOC NZ campsites from {self.campsites_url}")
            for campsite in doc_nz_campsite_request(
                request_url=self.campsites_url, bbox=bbox, limit=limit, offset=offset
            ):
                if enrich:
                    campsite = _enrich_campsite(self.api_url, t.cast("str", self.api_key), campsite)
                sources.append(
                    DocNzCampsiteHutSource(
                        name=campsite.get_name(),
                        source_data=campsite,
                        source_id=campsite.get_id(),
                        location=campsite.get_location(),
                        source_properties=DocNzCampsiteProperties(
                            bookable=campsite.bookable,
                            region=campsite.region,
                            place=campsite.place,
                            campsite_category=campsite.campsite_category,
                            page_uuid=_page_uuid(campsite.static_link),
                        ),
                    )
                )
        return sources

    def get_images(self, source_id: int | str) -> list[PhotoSchema]:
        """Hut/campsite page photos for one asset, independent of conversion.

        Use this to import huts without photos and fetch the (license-filtered)
        images separately: one cached page request per asset plus one partial
        download per photo. Unknown ids return `[]` (with a warning).

        Args:
            source_id: DOC assetId (doc_nz source id, int or str).

        Returns:
            Photos with licenses (CC or DOC/Crown only - third party (c) is skipped).
        """
        try:
            asset_id = int(str(source_id).strip())
        except ValueError:
            logger.warning("get_images: source id %r is not an assetId", source_id)
            return []
        static_link = _static_link_for(asset_id)
        if not static_link:
            logger.warning("get_images: no page link for assetId %s", source_id)
            return []
        try:
            return t.cast("list[PhotoSchema]", get_hut_images(static_link))
        except Exception as exc:  # photos are optional
            logger.warning("get_images: fetch failed for assetId %s: %r", source_id, exc)
            return []

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
        if isinstance(src, DocNzCampsiteHutSource) or (
            isinstance(src, t.Mapping) and src.get("source_name") == "doc_nz_camp"
        ):
            campsite_src = (
                DocNzCampsiteHutSource(**src) if isinstance(src, t.Mapping) else t.cast("DocNzCampsiteHutSource", src)
            )
            if campsite_src.source_data is None:
                err_msg = (
                    f"Conversion for '{campsite_src.source_name}' version {campsite_src.version} "
                    "without 'source_data' not allowed."
                )
                raise AttributeError(err_msg)
            return DocNzCampsite0Convert(include_photos=include_photos, source_data=campsite_src.source_data).get_hut()
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


class DocNzCampsiteService(BaseService[DocNzCampsiteHutSource]):
    """Service to get campsites from New Zealand's
    [Department of Conservation](https://www.doc.govt.nz)
    ([DOC Campsites open data](https://doc-deptconservation.opendata.arcgis.com/maps/doc-campsites)).

    Same infrastructure as [`DocNzService`][hut_services.doc_nz.service.DocNzService]:
    open-data layer without authentication (the campsites layer already
    ships introductions and categories), optional DOC API v2 enrichment
    (status/introduction) and a bulk alerts endpoint. Site counts
    (powered/unpowered) are NOT mapped to `capacity` — they live in `extras`.

    Note:
        The methods are described in [`BaseService`][hut_services.BaseService].
    """

    def __init__(
        self,
        request_url: str = DOC_NZ_CAMPSITES_URL,
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
    ) -> list[DocNzCampsiteHutSource]:
        """Get campsites from the DOC NZ open-data layer.

        Args:
            bbox: Boundary box.
            limit: Limit (how many entries to retrieve), `0` for all.
            offset: Offset of the request.
            enrich: Fetch status/introduction from the official DOC API v2
                for every campsite — one request per campsite (file-cached).
                `None` (default): enrich automatically when an API key is
                configured (`api_key` argument or `HUT_SRV_DOC_NZ_API_KEY`
                environment variable); `True`: require a key (raises without);
                `False`: never enrich. The layer already ships introduction
                and category, so enrichment adds little.

        Returns:
            Campsites from source.
        """
        logger.info(f"get DOC NZ campsites from {self.request_url}")
        campsites = doc_nz_campsite_request(request_url=self.request_url, bbox=bbox, limit=limit, offset=offset)
        if enrich is None:
            enrich = self.api_key is not None
        if enrich:
            if not self.api_key:
                msg = "DOC API key required for enrichment: pass `api_key` or set `HUT_SRV_DOC_NZ_API_KEY`."
                raise ValueError(msg)
            campsites = [self._enrich_campsite(campsite) for campsite in campsites]
        sources: list[DocNzCampsiteHutSource] = []
        for campsite in campsites:
            sources.append(
                DocNzCampsiteHutSource(
                    name=campsite.get_name(),
                    source_data=campsite,
                    source_id=campsite.get_id(),
                    location=campsite.get_location(),
                    source_properties=DocNzCampsiteProperties(
                        bookable=campsite.bookable,
                        region=campsite.region,
                        place=campsite.place,
                        campsite_category=campsite.campsite_category,
                        page_uuid=_page_uuid(campsite.static_link),
                    ),
                )
            )
        return sources

    def _enrich_campsite(self, campsite: DocNzCampsiteSchema) -> DocNzCampsiteSchema:
        """Merge DOC API v2 campsites detail fields into a layer campsite (best effort)."""
        if not self.api_key:
            return campsite
        return _enrich_campsite(self.api_url, self.api_key, campsite)

    def get_alerts(self) -> list[DocNzHutAlerts]:
        """Get current alerts for all campsites from the DOC API v2 (needs an API key).

        Returns:
            List of alerts per campsite (`assetId`, `name`, `alerts`).
        """
        if not self.api_key:
            msg = "DOC API key required for alerts: pass `api_key` or set `HUT_SRV_DOC_NZ_API_KEY`."
            raise ValueError(msg)
        alerts = doc_nz_alerts_request(self.api_url, self.api_key, kind="campsites")
        return t.cast("list[DocNzHutAlerts]", alerts)

    def convert(self, src: t.Mapping | t.Any, include_photos: bool = True) -> HutSchema:
        campsite_src = (
            DocNzCampsiteHutSource(**src)
            if isinstance(src, t.Mapping)
            else DocNzCampsiteHutSource.model_validate(src, from_attributes=True)
        )
        if campsite_src.version >= 0:
            if campsite_src.source_data is None:
                err_msg = (
                    f"Conversion for '{campsite_src.source_name}' version {campsite_src.version} "
                    "without 'source_data' not allowed."
                )
                raise AttributeError(err_msg)
            return DocNzCampsite0Convert(include_photos=include_photos, source_data=campsite_src.source_data).get_hut()
        else:
            err_msg = f"Conversion for '{campsite_src.source_name}' version {campsite_src.version} not implemented."
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
