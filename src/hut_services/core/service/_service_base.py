import typing as t

from pydantic import BaseModel

from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox

SourceT = t.TypeVar("SourceT", bound=BaseModel)


class BaseService(t.Generic[SourceT]):
    def __init__(
        self,
        support_bbox: bool = False,
        support_limit: bool = False,
        support_offset: bool = False,
        support_convert: bool = False,
    ) -> None:
        self._support_bbox = support_bbox
        self._support_limit = support_limit
        self._support_offset = support_offset
        self._support_convert = support_convert

    class MethodNotImplementedError(NotImplementedError):
        def __init__(self, obj: "BaseService", method: str):
            class_name = str(obj.__class__).replace("<class '", "").replace("'>", "")
            message = f"Service '{class_name}' method '{method}' is not implemented."
            super().__init__(message)

    @property
    def support_bbox(self) -> bool:
        return self._support_bbox

    @property
    def support_limit(self) -> bool:
        return self._support_limit

    @property
    def support_offset(self) -> bool:
        return self._support_offset

    @property
    def support_convert(self) -> bool:
        return self._support_convert

    def get_huts_from_source(
        self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict
    ) -> list[SourceT]:
        """Get all huts from openstreet map."""
        raise self.MethodNotImplementedError(self, "get_huts_from_source")

    def convert(self, src: SourceT) -> HutSchema:
        raise self.MethodNotImplementedError(self, "convert")

    def get_huts(self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict) -> list[HutSchema]:
        huts = []
        src_huts = self.get_huts_from_source(bbox=bbox, limit=limit, offset=offset, **kwargs)
        huts = [self.convert(h) for h in src_huts]
        return huts
