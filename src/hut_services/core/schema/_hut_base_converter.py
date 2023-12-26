from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

from ..guess import guess_slug_name
from ._contact import ContactSchema
from ._hut import HutSchema
from ._hut_fields import (
    CapacitySchema,
    HutTypeEnum,
    HutTypeSchema,
    OpenMonthlySchema,
    OwnerSchema,
    PhotoSchema,
)
from .geo import LocationEleSchema
from .locale import TranslationSchema

if __name__ == "__main__":  # only for testing
    from icecream import ic  # type: ignore[import-untyped] # noqa: F401, RUF100 , PGH003

TSourceData = TypeVar("TSourceData", bound=BaseModel)


class BaseHutConverterSchema(BaseModel, Generic[TSourceData]):
    """Base class used for a converter schema.

    Attributes:
        source: Source data

    All attributes as in [`HutSchema`][hut_services.core.schema.HutSchema] either as
    attribute or pydantic `computed_field`.

    Examples:
        See `hut_services.osm.schema.OsmHut0Convert`."""

    # See [`OsmHut0Convert`][hut_services.osm.schema.OsmHut0Convert].

    source: TSourceData = Field(..., exclude=True)

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

    @computed_field  # type: ignore[misc]
    @property
    def slug(self) -> str:
        return guess_slug_name(self.name.i18n)

    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        if hasattr(self.source, "get_name"):
            return TranslationSchema(de=self.source.get_name())
        raise self.FieldNotImplementedError(self, "name")

    @computed_field  # type: ignore[misc]
    @property
    def location(self) -> LocationEleSchema:
        if hasattr(self.source, "get_location"):
            return self.source.get_location()  # type: ignore  # noqa: PGH003
        raise self.FieldNotImplementedError(self, "location")

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        raise self.FieldNotImplementedError(self, "description")

    @computed_field  # type: ignore[misc]
    @property
    def notes(self) -> list[TranslationSchema]:
        return []

    @computed_field  # type: ignore[misc]
    @property
    def owner(self) -> OwnerSchema | None:
        return None

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def contacts(self) -> list[ContactSchema]:
        return []

    @computed_field  # type: ignore[misc]
    @property
    def country_code(self) -> str | None:
        return None

    @computed_field  # type: ignore[misc]
    @property
    def comment(self) -> str:
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def capacity(self) -> CapacitySchema:
        return CapacitySchema(open=None, closed=None)

    @computed_field(alias="type")  # type: ignore[misc]
    @property
    def hut_type(self) -> HutTypeSchema:
        return HutTypeSchema(open=HutTypeEnum.unknown, closed=None)

    @property
    def photos(self) -> list[PhotoSchema]:
        return []

    @computed_field()  # type: ignore[misc]
    @property
    def open_monthly(self) -> OpenMonthlySchema:
        return OpenMonthlySchema()  # pyright: ignore  # noqa: PGH003

    @computed_field  # type: ignore[misc]
    @property
    def is_active(self) -> bool:
        return True

    @computed_field  # type: ignore[misc]
    @property
    def is_public(self) -> bool:
        return True

    @computed_field  # type: ignore[misc]
    @property
    def extras(self) -> dict[str, Any]:
        return {}
