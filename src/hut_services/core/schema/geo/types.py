from typing import Annotated, TypeAlias

from geojson_pydantic.types import BBox, Position  # noqa: F401
from pydantic import Field

# WSG84
Elevation = Annotated[float, Field(ge=0, lt=9000, description="Elevation in meter")]
Longitude = Annotated[float, Field(ge=-180, le=180, examples=["7.6496971"], title="Longitude (x) in WGS84")]
Latitude = Annotated[float, Field(ge=-90, le=90, examples=["45.9765729"], title="Latitude (y) in WGS84")]

# LV03 (swiss)
LV03X = Annotated[float, Field()]  # ge=-90, le=90, examples=["45.9765729"], title="Latitude (y) in WGS84")]
LV03Y = Annotated[float, Field()]  # ge=-90, le=90, examples=["45.9765729"], title="Latitude (y) in WGS84")]
LV03: TypeAlias = tuple[LV03Y, LV03X, Elevation]
