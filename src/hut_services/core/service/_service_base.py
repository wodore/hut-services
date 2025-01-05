import datetime
import typing as t

from hut_services import HutSourceSchema, clear_file_cache
from hut_services.core.schema import HutBookingsSchema, HutSchema
from hut_services.core.schema.geo import BBox

THutSourceSchema = t.TypeVar("THutSourceSchema", bound=HutSourceSchema, covariant=True)


class BaseService(t.Generic[THutSourceSchema]):
    """Base service which is inheritated by other services.

    Warning:
        Do not use this directly.

    The following attributes are used to define which paramets are supported
    by a service.

    Attributes:
        support_bbox: Support for `bbox` as parameter.
        support_limit: Support for `limit` as parameter.
        support_offset: Support for `offset` as parameter.
        support_convert: Support for `convert` as parameter.

    Examples:
        Custom service base in `BaseService`.
        For this the two schemas `MyHutSource` and `MyInfoHutConvert` need to be defined as well.
        ```python
        from typing import Any
        from hut_services.core.schema.geo import BBox
        from hut_services import BaseService, HutSchema

        # TODO: define this somewhere:
        from my_service.schema import MyHutSource, MyInfoHutConvert

        class MyService(BaseService[MyHutSource]):
            def __init__(self, request_url: str = "http://hut.info"):
                super().__init__(support_bbox=True,
                                 support_limit=True,
                                 support_offset=True,
                                 support_convert=True)
                self.request_url = request_url

            def get_huts_from_source(
                self, bbox: BBox | None = None, limit: int = 1,
                offset: int = 0, **kwargs: Any
            ) -> list[MyHutSource]:
                src_huts = httpx.get(self.request_url)
                return [MyHutSource(**h) for h in src_huts]

            def convert(self, src: MyHutSource) -> HutSchema:
                return MyInfoHutConvert(source=src.source_data).get_hut()
        ```
    """

    support_bbox: bool = False
    support_limit: bool = False
    support_offset: bool = False
    support_convert: bool = False
    support_booking: bool = False

    def __init__(
        self,
        support_bbox: bool = False,
        support_limit: bool = False,
        support_offset: bool = False,
        support_convert: bool = False,
        support_booking: bool = False,
    ) -> None:
        self.support_bbox = support_bbox
        self.support_limit = support_limit
        self.support_offset = support_offset
        self.support_convert = support_convert
        self.support_booking = support_booking

    @classmethod
    def clear_all_cache(cls) -> None:
        """Clears the cache of all services!"""
        clear_file_cache()

    def get_huts_from_source(
        self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: t.Any
    ) -> list[THutSourceSchema]:
        """Get all huts from source.

        Args:
            bbox: Boundary box.
            limit: Limit (how many entries to retrieve).
            offset: Offset of the request.

        Returns:
            Huts from source.
        """
        raise self.MethodNotImplementedError(self, "get_huts_from_source")

    def convert(self, src: t.Mapping | t.Any, include_photos: bool = True) -> HutSchema:
        """Convert one hut from source to [`HutSchema`][hut_services.HutSchema].

        Args:
            src: Source schema.
            include_photos: Include photos, some service need additonal requests to get the photos.

        Returns:
            Converted hut.
        """
        # example:
        # hut_src = OsmHutSource(**src) if isinstance(src, t.Mapping) else OsmHutSource.model_validate(src)
        raise self.MethodNotImplementedError(self, "convert")

    def get_huts(
        self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, include_photos: bool = True, **kwargs: t.Any
    ) -> list[HutSchema]:
        """Get all huts form source and converts them.
        Calls [`get_huts_from_source()`][hut_services.BaseService.get_huts_from_source]
        and [`convert()`][hut_services.BaseService.convert].

        Returns:
            Converted huts from source."""
        huts = []
        src_huts = self.get_huts_from_source(bbox=bbox, limit=limit, offset=offset, **kwargs)
        huts = [self.convert(h, include_photos=include_photos) for h in src_huts]
        return huts

    def get_bookings(
        self,
        date: datetime.datetime | datetime.date | t.Literal["now"] | None = None,
        days: int | None = None,
        source_ids: list[int] | None = None,
        lang: str = "de",
    ) -> dict[int, HutBookingsSchema]:
        """Get bookings for a list of huts.

        Args:
            date: Start daye for the bookings
            days: Duration in days
            source_ids: A list of ids to return (source id, not the hut id), if set to `None` all are returned

        Returns:
            A dictionary with the bookings (key = soruce id).
        """
        raise self.MethodNotImplementedError(self, "get_bookings")

    class MethodNotImplementedError(NotImplementedError):
        """Method is not implemented exception.

        Args:
            obj: Service object (e.g. `MyService`).
            method: Method which is not implemented.
        """

        def __init__(self, obj: "BaseService", method: str):
            class_name = str(obj.__class__).replace("<class '", "").replace("'>", "")
            message = f"Service '{class_name}' method '{method}' is not implemented."
            super().__init__(message)
