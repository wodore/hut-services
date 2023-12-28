import logging
from typing import Any

from pydantic import BaseModel, Field, computed_field

from hut_services import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    LocationEleSchema,
    PhotoSchema,
    SourcePropertiesSchema,
    TranslationSchema,
)
from hut_services.core.schema.geo.types import Latitude, Longitude

logger = logging.getLogger(__name__)


class WikidataHutSchema(BaseModel):
    """Open street map schema."""

    attributes: dict[str, Any]
    photos: list[PhotoSchema]
    wikidata_id: str = Field(..., alias="id")
    name: str
    lat: Latitude | None
    lon: Longitude | None

    def get_id(self) -> str:
        """Get open street map `id`."""
        return str(self.wikidata_id)

    def get_name(self) -> str:
        """Get open street map hut name."""
        return self.name

    def get_location(self) -> LocationEleSchema:
        """Get open street map location."""
        if self.lat is not None and self.lon is not None:
            return LocationEleSchema(lat=self.lat, lon=self.lon)
        else:
            return LocationEleSchema(lat=0, lon=0)


class WikidataProperties(SourcePropertiesSchema):
    pass


class WikidataHutSource(BaseHutSourceSchema[WikidataHutSchema, WikidataProperties]):
    version: int = 0
    source_name: str = "wikidata"


class WikidataHut0Convert(BaseHutConverterSchema[WikidataHutSchema]):
    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(de=self.source.get_name())

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema()

    @computed_field()  # type: ignore[misc]
    @property
    def photos(self) -> list[PhotoSchema]:
        return self.source.photos
