import logging

from pydantic import BaseModel, Field, computed_field

from hut_services import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    LocationEleSchema,
    SourcePropertiesSchema,
    TranslationSchema,
)
from hut_services.core.schema.geo import BBox
from hut_services.core.schema.geo.types import Latitude, Longitude
from hut_services.osm.schema import OSMTagsOptional

# from hut_services.wikidata.service import WikidataEntity  # , wikidata_service


logger = logging.getLogger(__name__)


class GeocodeHutSchema(BaseModel):
    """Open street map schema."""

    place_id: int | None = None
    name: str
    lat: Latitude
    lon: Longitude
    licence: str | None = None
    osm_type: str | None = None
    osm_id: int | None = None
    category: str | None = None
    building_type: str | None = Field(None, alias="type")
    place_rank: int | None = None
    importance: float | None = None
    addresstype: str | None = None
    display_name: str | None = None
    extratags: OSMTagsOptional | None = None
    boundingbox: BBox | None = None  # ['47.0545528', '47.0548247', '11.1981883', '11.1984526']

    def get_id(self) -> str:
        """Get open street map `id`."""
        return str(self.place_id)

    def get_name(self) -> str:
        """Get open street map hut name."""
        return self.name

    def get_location(self) -> LocationEleSchema:
        """Get open street map location."""
        _tags = self.extratags if self.extratags else OSMTagsOptional()  # pyright: ignore  # noqa: PGH003
        try:
            ele = float(_tags.ele)  # type: ignore  # noqa: PGH003
        except (ValueError, TypeError):
            ele = None
        return LocationEleSchema(lat=self.lat, lon=self.lon, ele=ele)


class GeocodeProperties(SourcePropertiesSchema):
    pass


class GeocodeHutSource(BaseHutSourceSchema[GeocodeHutSchema, GeocodeProperties]):
    version: int = 0
    source_name: str = "geocode"


class GeocodeHut0Convert(BaseHutConverterSchema[GeocodeHutSchema]):
    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(de=self.source.get_name())

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema()
