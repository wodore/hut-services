from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

from ..guess import guess_slug_name
from ._contact import ContactSchema
from ._hut import HutSchema
from ._hut_base_source import SourceDataSchema
from ._hut_fields import (
    CapacitySchema,
    HutTypeEnum,
    HutTypeSchema,
    OpenMonthlySchema,
    OwnerSchema,
)
from ._license import AuthorSchema, SourceSchema
from ._photo import PhotoSchema
from .geo import LocationEleSchema
from .locale import TranslationSchema

if __name__ == "__main__":  # only for testing
    from icecream import ic  # type: ignore[import-untyped] # noqa: F401, RUF100 , PGH003


TSourceData = TypeVar("TSourceData", bound=SourceDataSchema)


class BaseHutConverterSchema(BaseModel, Generic[TSourceData]):
    """Base class used for a converter schema.

    Attributes:
        source: Source data

    All attributes as in [`HutSchema`][hut_services.core.schema.HutSchema] either as
    attribute or pydantic `computed_field`.

    Examples:
        See `hut_services.osm.schema.OsmHut0Convert`."""

    # See [`OsmHut0Convert`][hut_services.osm.schema.OsmHut0Convert].

    source_data: TSourceData = Field(..., exclude=True)
    include_photos: bool = True

    class FieldNotImplementedError(Exception):
        """Field is not implemented.

        Args:
            obj: Current object.
            field: Field which is not implementd."""

        def __init__(self, obj: "BaseHutConverterSchema", field: str):
            class_name = str(obj.__class__).replace("<class '", "").replace("'>", "")
            message = f"Converter '{class_name}' field '{field}' is not implemented."
            super().__init__(message)

    def get_hut(self) -> HutSchema:
        """Convert to hut.

        Returns:
            Converted hut."""
        hut_dict = self.model_dump(by_alias=True)
        return HutSchema(**hut_dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        return guess_slug_name(self.name.i18n)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> TranslationSchema:
        if hasattr(self.source_data, "get_name"):
            return TranslationSchema(de=self.source_data.get_name())
        raise self.FieldNotImplementedError(self, "name")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> SourceSchema | None:
        if hasattr(self.source_data, "get_name"):
            return SourceSchema(name=self.source_name, ident=self.source_data.get_id())
        raise self.FieldNotImplementedError(self, "origin")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def author(self) -> AuthorSchema | None:
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_name(self) -> str:
        # TODO: how to get source_name
        # if hasattr(self.source_data, "source_name"):
        #     return self.source_data.source_name
        raise self.FieldNotImplementedError(self, "source_name")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def location(self) -> LocationEleSchema:
        if hasattr(self.source_data, "get_location"):
            return self.source_data.get_location()  # type: ignore  # noqa: PGH003
        raise self.FieldNotImplementedError(self, "location")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> TranslationSchema:
        raise self.FieldNotImplementedError(self, "description")

    # @computed_field  # type: ignore[prop-decorator]
    # @property
    # def description_attribution(self) -> str:
    #    return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def notes(self) -> list[TranslationSchema]:
        return []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def owner(self) -> OwnerSchema | None:
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def contacts(self) -> list[ContactSchema]:
        return []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def country_code(self) -> str | None:
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def comment(self) -> str:
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capacity(self) -> CapacitySchema:
        return CapacitySchema(open=None, closed=None)

    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def hut_type(self) -> HutTypeSchema:
        return HutTypeSchema(open=HutTypeEnum.unknown, closed=None)

    @property
    def photos(self) -> list[PhotoSchema]:
        return []

    @computed_field()  # type: ignore[prop-decorator]
    @property
    def open_monthly(self) -> OpenMonthlySchema:
        return OpenMonthlySchema()  # pyright: ignore  # noqa: PGH003

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_active(self) -> bool:
        return True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_public(self) -> bool:
        return True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def extras(self) -> dict[str, Any]:
        return {}
