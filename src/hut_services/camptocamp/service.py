#!/usr/bin/env python
"""Camptocamp.org service for retrieving hut data."""

import json
import logging
import typing as t
from time import sleep

try:
    from pyproj import Transformer
except ImportError:
    Transformer: type[object] | None = None  # type: ignore[no-redef]

try:
    import httpx

    USE_HTTPX = True
except ImportError:
    import requests

    USE_HTTPX = False

from hut_services.camptocamp.schema import (
    CamptocampApiResponse,
    CamptocampDocument,
    CamptocampHut0Convert,
    CamptocampHutSource,
    CamptocampProperties,
)
from hut_services.core.cache import file_cache
from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox
from hut_services.core.service import BaseService

if __name__ == "__main__":  # only for testing
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


@file_cache()
def camptocamp_detail_request(
    url: str,
    document_id: int,
    **params: t.Any,
) -> CamptocampDocument | None:
    """
    Request detailed information for a specific hut from Camptocamp API.

    Args:
        url: Base API URL (without document ID)
        document_id: The document ID to fetch
        **params: Additional query parameters

    Returns:
        CamptocampDocument with detailed information or None if failed
    """
    detail_url = f"{url}/{document_id}"

    try:
        if USE_HTTPX:
            r = httpx.get(detail_url, params=params, timeout=30)
            r.raise_for_status()
            logger.debug(f"Request detail URL: {r.url}")
        else:
            r = requests.get(detail_url, params=params, timeout=30)  # type: ignore[assignment]
            r.raise_for_status()
            logger.debug(f"Request detail URL: {r.url}")

        data = r.json()

        # Parse the geometry coordinates from projected to lat/lon if we have pyproj
        if Transformer is not None and "geometry" in data and "geom" in data["geometry"]:
            try:
                transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                geom_str = data["geometry"]["geom"]
                geom_data = json.loads(geom_str)
                if geom_data.get("type") == "Point" and "coordinates" in geom_data:
                    # Convert from Web Mercator to WGS84
                    x, y = geom_data["coordinates"]
                    lon, lat = transformer.transform(x, y)
                    geom_data["coordinates"] = [lon, lat]
                    data["geometry"]["geom"] = json.dumps(geom_data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to convert coordinates for document {document_id}: {e}")

        return CamptocampDocument(**data)

    except Exception as e:
        if (USE_HTTPX and isinstance(e, httpx.HTTPError)) or (
            not USE_HTTPX and isinstance(e, requests.exceptions.RequestException)
        ):
            logger.exception(f"HTTP error occurred fetching detail for {document_id}")
        else:
            logger.exception(f"Error fetching detail data for document {document_id}")
        return None


@file_cache()
def camptocamp_request(
    url: str,
    waypoint_type: str = "hut",
    limit: int | None = None,
    offset: int = 0,
    bbox: BBox | None = None,
    **params: t.Any,
) -> CamptocampApiResponse:
    """
    Request huts from Camptocamp API.

    Args:
        url: Base API URL
        waypoint_type: Type of waypoint to fetch (default: "hut")
        limit: Maximum number of results
        offset: Offset for pagination
        bbox: Bounding box for geographic filtering
        **params: Additional query parameters

    Returns:
        CamptocampApiResponse with documents
    """
    # Build query parameters
    params["wtyp"] = waypoint_type

    if limit is not None:
        params["limit"] = limit

    if offset > 0:
        params["offset"] = offset

    if bbox:
        # Camptocamp expects bbox as: west,south,east,north
        params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    # Make request
    try:
        if USE_HTTPX:
            r = httpx.get(url, params=params, timeout=30)
            r.raise_for_status()
        else:
            r = requests.get(url, params=params, timeout=30)  # type: ignore[assignment]
            r.raise_for_status()
        logger.debug(f"Request URL: {r.url}")

        data = r.json()

        # Parse the geometry coordinates from projected to lat/lon if we have pyproj
        if Transformer is not None:
            transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

            for doc in data.get("documents", []):
                if "geometry" in doc and "geom" in doc["geometry"]:
                    try:
                        geom_str = doc["geometry"]["geom"]
                        geom_data = json.loads(geom_str)
                        if geom_data.get("type") == "Point" and "coordinates" in geom_data:
                            # Convert from Web Mercator to WGS84
                            x, y = geom_data["coordinates"]
                            lon, lat = transformer.transform(x, y)
                            geom_data["coordinates"] = [lon, lat]
                            doc["geometry"]["geom"] = json.dumps(geom_data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to convert coordinates for document {doc.get('document_id')}: {e}")

        return CamptocampApiResponse(**data)

    except Exception as e:
        if (USE_HTTPX and isinstance(e, httpx.HTTPError)) or (
            not USE_HTTPX and isinstance(e, requests.exceptions.RequestException)
        ):
            logger.exception("HTTP error occurred")
        else:
            logger.exception("Error fetching data from Camptocamp")
        return CamptocampApiResponse(documents=[])


class CamptocampService(BaseService[CamptocampHutSource]):
    """
    Service to get huts from [Camptocamp.org](https://www.camptocamp.org)
    using their [API](https://api.camptocamp.org).

    Note:
        The methods are described in [`BaseService`][hut_services.BaseService].
    """

    def __init__(self, request_url: str = "https://api.camptocamp.org/waypoints"):
        super().__init__(support_bbox=True, support_limit=True, support_offset=True, support_convert=True)
        self.request_url = request_url

    def get_huts_from_source(
        self,
        bbox: BBox | None = None,
        limit: int = 100,
        offset: int = 0,
        fetch_details: bool = True,
        request_interval: float = 0.5,
        **kwargs: t.Any,
    ) -> list[CamptocampHutSource]:
        """
        Get huts from Camptocamp API.

        Args:
            bbox: Bounding box for geographic filtering
            limit: Maximum number of results
            offset: Offset for pagination
            fetch_details: Whether to fetch detailed information for each hut
            request_interval: Delay in seconds between detail requests (to be nice to the API)
            **kwargs: Additional parameters

        Returns:
            List of CamptocampHutSource objects
        """
        logger.info(f"Getting Camptocamp data from {self.request_url}")

        # Request data from API
        response = camptocamp_request(
            url=self.request_url, waypoint_type="hut", limit=limit, offset=offset, bbox=bbox, **kwargs
        )

        huts = []
        for idx, document in enumerate(response.documents):
            try:
                # Create CamptocampDocument from the raw data
                camptocamp_doc = CamptocampDocument.model_validate(document)

                # If fetch_details is enabled, get detailed information
                if fetch_details:
                    logger.debug(f"Fetching details for document {camptocamp_doc.document_id}")
                    detailed_doc = camptocamp_detail_request(
                        url=self.request_url, document_id=camptocamp_doc.document_id
                    )

                    if detailed_doc:
                        camptocamp_doc = detailed_doc
                    else:
                        logger.warning(
                            f"Failed to fetch details for document {camptocamp_doc.document_id}, using basic info"
                        )

                    # Be nice to the API - add a small delay between requests
                    if idx < len(response.documents) - 1:  # Don't sleep after the last request
                        sleep(request_interval)

                # Create properties
                properties = CamptocampProperties(
                    quality=camptocamp_doc.quality or "unknown", waypoint_type=camptocamp_doc.waypoint_type or "hut"
                )

                # Create source object
                hut = CamptocampHutSource(
                    name=camptocamp_doc.get_name(),
                    source_id=camptocamp_doc.get_id(),
                    location=camptocamp_doc.get_location(),
                    source_data=camptocamp_doc,
                    source_properties=properties,
                )
                huts.append(hut)

            except Exception as e:
                logger.warning(f"Failed to process document: {e}")
                continue

        logger.info(f"Successfully got {len(huts)} huts")
        return huts

    def convert(self, src: t.Mapping | t.Any, include_photos: bool = True) -> HutSchema:
        """
        Convert CamptocampHutSource to HutSchema.

        Args:
            src: Source data (CamptocampHutSource or dict)
            include_photos: Whether to include photos

        Returns:
            HutSchema object
        """
        hut_src = (
            CamptocampHutSource(**src)
            if isinstance(src, t.Mapping)
            else CamptocampHutSource.model_validate(src, from_attributes=True)
        )

        if hut_src.version >= 0:
            if hut_src.source_data is None:
                err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} without 'source_data' not allowed."
                raise AttributeError(err_msg)

            return CamptocampHut0Convert(source_data=hut_src.source_data, include_photos=include_photos).get_hut()
        else:
            err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} not implemented."
            raise NotImplementedError(err_msg)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)

    # Test the service
    service = CamptocampService()

    # Test with a small limit
    limit = 5
    huts = service.get_huts_from_source(limit=limit)

    for hut_source in huts:
        try:
            # Convert to HutSchema
            hut = service.convert(hut_source, include_photos=False)

            rprint("=" * 50)
            rprint(f"Name: {hut.name.i18n}")
            rprint(f"Location: {hut.location}")
            rprint(f"URL: {hut.url}")
            if hut.description.i18n:
                rprint(f"Description: {hut.description.i18n[:200]}...")
            rprint(f"Type: {hut.hut_type}")
            rprint(f"Capacity: {hut.capacity}")

        except Exception as e:
            rprint(f"Error converting hut: {e}")
