#!/usr/bin/env python
# from functools import lru_cache
import json
import logging
import typing as t

import httpx
import xmltodict
from easydict import EasyDict  # type: ignore[import-untyped]

from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox
from hut_services.core.service import BaseService
from hut_services.refuges_info.massif import MASSIF_ALPES
from hut_services.refuges_info.schema import (
    RefugesInfoFeatureCollection,
    RefugesInfoHut0Convert,
    RefugesInfoHutSource,
)

if __name__ == "__main__":  # only for testing
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


def refuges_info_request(
    url: str,
    limit: str | int = "all",
    type_points: t.Sequence[int] = [7, 10, 9, 28],
    massif: t.Sequence[int] | None = MASSIF_ALPES,
    bbox: BBox | None = None,
    text_format: t.Literal["texte", "markdown", "html"] = "markdown",
    output_format: t.Literal["geojson", "xml", "csv"] = "geojson",
    detail: bool = True,
    **params: t.Any,
) -> RefugesInfoFeatureCollection | t.Any | bytes:
    # https://www.refuges.info/api/massif?nb_points=all&format=xml&type_points=7,10,9,28&massif=12,339,407,45,342,20,29,343,412,8,344,408,432,406,52,9
    params["nb_points"] = limit
    params["type_points"] = ",".join([str(t) for t in type_points])
    params["format"] = output_format
    params["format_texte"] = text_format
    params["detail"] = "complet" if detail else "simple"
    if massif and bbox:
        raise NotImplementedError("Either 'massif', or 'bbox' required, both together are not supported.")
    if massif:
        params["massif"] = ",".join([str(m) for m in massif])
        url = url + "/massif"
    elif bbox:
        params["bbox"] = ",".join([str(m) for m in bbox])
        url = url + "/bbox"
    else:
        raise NotImplementedError("Either 'massif', or 'bbox' required.")
    r = httpx.get(url, params=params, timeout=10)
    logger.debug(f"request url: {r.url}")
    if output_format == "geojson":
        data = json.loads(r.content)
        return RefugesInfoFeatureCollection(**data)
    if output_format == "xml":
        return EasyDict(xmltodict.parse(r.content))
    return r.content


class RefugesInfoService(BaseService[RefugesInfoHutSource]):
    """Service to get huts from
    [refuges.info](https://www.refuges.info)
    with [its api](https://www.refuges.info/api).

    Note:
        The methods are descriebed in [`BaseService`][hut_services.BaseService].

    """

    def __init__(self, request_url: str = "https://www.refuges.info/api"):
        super().__init__(support_bbox=True, support_limit=True, support_offset=False, support_convert=True)
        self.request_url = request_url

    def get_huts_from_source(
        self,
        bbox: BBox | None = None,
        limit: int = 1,
        offset: int = 0,
        # type_points: Sequence[int] = [7, 10, 9, 28],
        # massif: Sequence[int] = [12, 339, 407, 45, 342, 20, 29, 343, 412, 8, 344, 408, 432, 406, 52, 9],
        **kwargs: t.Any,
    ) -> list[RefugesInfoHutSource]:
        type_points: t.Sequence[int] = kwargs.get("type_points", [7, 10, 9, 28])
        massif: t.Sequence[int] | None = kwargs.get("massif", MASSIF_ALPES if not bbox else None)
        # "massif", [12, 339, 407, 45, 342, 20, 29, 343, 412, 8, 344, 408, 432, 406, 52, 9] if not bbox else None

        logger.info(f"get refuges.info data from {self.request_url}")
        fc: RefugesInfoFeatureCollection = refuges_info_request(
            url=self.request_url, bbox=bbox, limit=limit, type_points=type_points, massif=massif, detail=True, **kwargs
        )  # type: ignore  # noqa: PGH003
        huts = []
        for feature in fc.features:
            refuges_hut = RefugesInfoHutSource(
                name=feature.get_name(),
                source_data=feature,
                source_id=feature.get_id(),
                location=feature.get_location(),
                source_properties=feature.get_properties(),
            )
            huts.append(refuges_hut)
        logger.info(f"succesfully got {len(huts)} huts")
        return huts

    def convert(self, src: t.Mapping | t.Any) -> HutSchema:
        hut_src = (
            RefugesInfoHutSource(**src)
            if isinstance(src, t.Mapping)
            else RefugesInfoHutSource.model_validate(src, from_attributes=True)
        )
        if hut_src.version >= 0:
            if hut_src.source_data is None:
                err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} without 'source_data' not allowed."
                raise AttributeError(err_msg)
            return RefugesInfoHut0Convert(source_data=hut_src.source_data).get_hut()
        else:
            err_msg = f"Conversion for '{hut_src.source_name}' version {hut_src.version} not implemented."
            raise NotImplementedError(err_msg)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
    limit = 10000
    service = RefugesInfoService()
    bbox_ch = None  # (6.02260949059, 45.7769477403, 10.4427014502, 47.8308275417)
    huts = service.get_huts_from_source(limit=limit, bbox=bbox_ch)
    for h in huts:
        # rprint(h)
        hut = service.convert(h)
        rprint(hut.name)
        print(hut.description.fr[:250])
        # rprint(h.source_properties_schema)
        # rprint(h)
        # print(h.show(source_name=False))
