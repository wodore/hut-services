import logging
from typing import Any

from pydantic import Field, computed_field

from hut_services import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    LocationEleSchema,
    PhotoSchema,
    SourcePropertiesSchema,
    TranslationSchema,
)
from hut_services.core.schema import BaseSchema
from hut_services.core.schema._license import LicenseSchema, SourceSchema
from hut_services.core.schema.geo.types import Latitude, Longitude
from hut_services.wikicommons.service import wikicommons_service

logger = logging.getLogger(__name__)


class WikidataPhotoInfo(BaseSchema):
    size: int
    width: int
    height: int
    url: str
    descriptionurl: str
    descriptionshorturl: str
    mime: str


class WikidataPhotoAttributes(BaseSchema):
    ns: int
    title: str
    missing: str
    known: str
    imagerepository: str
    imageinfo: list[WikidataPhotoInfo]
    contentmodel: str
    pagelanguage: str
    pagelanguagehtmlcode: str
    pagelanguagedir: str
    fullurl: str
    editurl: str
    canonicalurl: str


class WikidataPhoto(BaseSchema):
    """Wikidata photo."""

    title: str
    attributes: WikidataPhotoAttributes


class WikidataHutSchema(BaseSchema):
    """Open street map schema."""

    attributes: dict[str, Any]
    photo: WikidataPhoto | None
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
        return TranslationSchema(de=self.source_data.get_name())

    @computed_field  # type: ignore[misc]
    @property
    def source_name(self) -> str:
        return "wikidata"

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema()

    @computed_field()  # type: ignore[misc]
    @property
    def photos(self) -> list[PhotoSchema]:
        image = self.source_data.photo
        if image is None:
            return []
        return [wikicommons_service.get_photo(image.title.replace("File:", ""))]

    @computed_field  # type: ignore[misc]
    @property
    def source(self) -> SourceSchema | None:
        if hasattr(self.source_data, "get_name"):
            return SourceSchema(
                name=self.source_name,
                ident=self.source_data.get_id(),
                url=f"https://www.wikidata.org/wiki/{self.source_data.wikidata_id}",
            )
        raise self.FieldNotImplementedError(self, "origin")

    @computed_field  # type: ignore[misc]
    @property
    def license(self) -> LicenseSchema | None:  # noqa: A003
        return LicenseSchema(
            slug="cc-by-sa-4.0", name="CC-BY-SA 4.0", url="https://creativecommons.org/licenses/by-sa/4.0/"
        )
