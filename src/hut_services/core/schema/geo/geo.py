from typing import Tuple

from geojson_pydantic import Feature, FeatureCollection, Point  # noqa: F401
from geojson_pydantic.types import BBox, Position  # noqa: F401
from pydantic import BaseModel

from hut_services.core.utils import GPSConverter

from .types import Elevation, Latitude, Longitude


class LocationSchema(BaseModel):
    """Location with longitude, latitude and optional elevation in WSG84"""

    lat: Latitude
    lon: Longitude
    ele: Elevation | None = None

    @classmethod
    def from_swiss(cls, ch_lat: float, ch_lon: float, ele: float | None) -> "LocationSchema":
        """
        Takes LV03 or LV95 (newest) coordiates.
        More information:
            https://en.wikipedia.org/wiki/Swiss_coordinate_system
        """
        if ele is None:
            ele = 0
        if ch_lat > 2000000:
            ch_lat -= 2000000
        if ch_lon > 1000000:
            ch_lon -= 1000000
        converter = GPSConverter()
        ch_lat, ch_lon, ele = converter.LV03toWGS84(ch_lat, ch_lon, ele)
        return cls(lat=ch_lat, lon=ch_lon, ele=ele)

    @property
    def lon_lat(self) -> Tuple[Longitude, Latitude]:
        return (self.lon, self.lat)

    @property
    def lon_lat_ele(self) -> Tuple[Longitude, Latitude, Elevation]:
        """Return tuple with longitude, latitude and elevation. If elevation is not defined it returns 0."""
        ele = self.ele if self.ele else 0
        return (self.lon, self.lat, ele)

    @property
    def geojson(self) -> Point:
        if self.ele:
            return Point(coordinates=self.lon_lat_ele, type="Point")
        return Point(coordinates=self.lon_lat, type="Point")

    def __str__(self) -> str:
        return f"lon={self.lon},lat={self.lat},ele={self.ele}"