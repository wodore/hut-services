import typing as t

from geojson_pydantic import Feature, FeatureCollection, Point  # noqa: F401
from geojson_pydantic.types import BBox, Position  # noqa: F401
from pydantic import BaseModel, ConfigDict, model_validator

from hut_services.core.utils import GPSConverter

from .types import Elevation, Latitude, Longitude


class LocationSchema(BaseModel):
    """Location with longitude, latitude and optional elevation in WSG84.

    Attributes:
        lat: Latitude.
        lon: Longitude.
        ele: Elevation in meter.
    """

    model_config = ConfigDict(from_attributes=True)

    lat: Latitude
    lon: Longitude
    # ele: Elevation | None = None

    @model_validator(mode="before")
    @classmethod
    def check_field_aliases(cls, data: t.Any) -> t.Any:
        for field, alias in [("lat", "x"), ("lon", "y"), ("ele", "z")]:
            if isinstance(data, dict) and alias in data and field not in data:
                data[field] = data[alias]
            elif hasattr(data, alias) and not hasattr(data, field):
                setattr(data, field, getattr(data, alias))
        return data

    @classmethod
    def from_swiss(cls, ch_lat: float, ch_lon: float, ele: float | None) -> "LocationSchema | LocationEleSchema":
        """Takes LV03 or LV95 (newest) coordiates.
        [More information](https://en.wikipedia.org/wiki/Swiss_coordinate_system).

        Args:
            ch_lat: Latitude in swiss format (east).
            ch_lon: Longitude in swiss format (north).
            ele: Elevation in meter.

        Returns:
            `LocationSchema` object.
        """
        if ele is None:
            ele = 0
        if ch_lat > 2000000:
            ch_lat -= 2000000
        if ch_lon > 1000000:
            ch_lon -= 1000000
        converter = GPSConverter()
        ch_lat, ch_lon, ele = converter.LV03toWGS84(ch_lat, ch_lon, ele)
        return cls(lat=ch_lat, lon=ch_lon)

    @property
    def lon_lat(self) -> tuple[Longitude, Latitude]:
        """Tuple with (`longitude`, `latitude`).

        Returns:
            Longitude and latitude.
        """
        return (self.lon, self.lat)

    @property
    def geojson(self) -> Point:
        """Retuns as geojson point."""
        return Point(coordinates=self.lon_lat, type="Point")

    def __str__(self) -> str:
        return f"lon={self.lon},lat={self.lat}"


class LocationEleSchema(LocationSchema):
    """Location with longitude, latitude and (optional) elevation in WSG84.

    Attributes:
        lat: Latitude.
        lon: Longitude.
        ele: Elevation in meter.
    """

    model_config = ConfigDict(from_attributes=True)

    ele: Elevation | None = None

    @classmethod
    def from_swiss(cls, ch_lat: float, ch_lon: float, ele: float | None) -> "LocationEleSchema":
        loc = super().from_swiss(ch_lat=ch_lat, ch_lon=ch_lon, ele=ele)
        return LocationEleSchema(lat=loc.lat, lon=loc.lon, ele=ele)

    @property
    def lon_lat_ele(self) -> tuple[Longitude, Latitude, Elevation]:
        """Tuple with longitude, latitude and elevation. If elevation is not defined it returns 0.

        Returns:
            Longitude, latitude and elevation."""
        ele = self.ele if self.ele else 0
        return (self.lon, self.lat, ele)

    @property
    def geojson(self) -> Point:
        """Retuns as geojson point."""
        return Point(coordinates=self.lon_lat_ele, type="Point")

    def __str__(self) -> str:
        return f"lon={self.lon},lat={self.lat},ele={self.ele}"
