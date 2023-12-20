from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

from hut_services.core.schema import CapacitySchema, ContactSchema, HutSchema, OwnerSchema
from hut_services.core.schema.locale import TranslationSchema

from .geo import LocationSchema

TSourceData = TypeVar("TSourceData", bound=BaseModel)


class BaseHutConverterSchema(BaseModel, Generic[TSourceData]):
    """Base class used for a converter schema.

    Attributes:
        source: Source data

    All attributes as in [`HutSchema`][hut_services.core.schema.HutSchema] either as
    attribute or pydantic `computed_field`.

    Examples:
        See [`OsmHut0Convert`][hut_services.osm.schema.OsmHut0Convert]."""

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
        raise self.FieldNotImplementedError(self, "slug")

    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        if hasattr(self.source, "get_name"):
            return TranslationSchema(de=self.source.get_name())
        raise self.FieldNotImplementedError(self, "name")

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
    def comment(self) -> str:
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def extras(self) -> dict[str, Any]:
        return {}

    @computed_field  # type: ignore[misc]
    @property
    def location(self) -> LocationSchema:
        if hasattr(self.source, "get_location"):
            return self.source.get_location()  # type: ignore  # noqa: PGH003
        raise self.FieldNotImplementedError(self, "location")

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def capacity(self) -> CapacitySchema:
        return CapacitySchema(opened=None, closed=None)

    @computed_field(alias="type")  # type: ignore[misc]
    @property
    def hut_type(self) -> str:
        return "unknown"

    @computed_field  # type: ignore[misc]
    @property
    def owner(self) -> OwnerSchema | None:
        return None

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
    def contacts(self) -> list[ContactSchema]:
        return []
