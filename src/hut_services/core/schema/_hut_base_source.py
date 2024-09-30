from datetime import datetime
from typing import Generic, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ._base import BaseSchema
from .geo import LocationEleSchema


class SourcePropertiesSchema(BaseModel):
    """Properties saved together with the source data.

    Examples:
        See `hut_services.osm.schema.OsmProperties`."""

    # See [`OsmProperties`][hut_services.osm.schema.OsmProperties]."""


class SourceDataSchema(BaseSchema):
    """SourceData schema"""

    def get_id(self) -> str:
        """Get source `id`."""
        raise NotImplementedError("'get_id()' not implemented")

    def get_name(self) -> str:
        """Get source hut `name`."""
        raise NotImplementedError("'get_name()' not implemented")


TSourceData_co = TypeVar("TSourceData_co", bound=SourceDataSchema, covariant=True)
TProperties_co = TypeVar("TProperties_co", bound=SourcePropertiesSchema, covariant=True)


class BaseHutSourceSchema(BaseModel, Generic[TSourceData_co, TProperties_co]):
    """Base class for a hut source.

    Attributes:
        source_name: Name of the source (e.g. osm, wikipedia, ...).
        name: Original hut name.
        location: Location of the hut.
        source_id: Originial source id of the hut.
        source_data: Source data for this hut.
        source_properties: Additinal source data properties.
        version: Version of the service when this entry was created.
        created: Created.

    Examples:
        ``` py
        class MyHutSource(BaseHutSourceSchema[MyHutSchema, SourcePropertiesSchema]):
            source_name: str = "my"
        ```

        Or with different properties: `hut_services.osm.schema.OsmHutSource`.
    """

    # Or with different properties: [`OsmHutSource`][hut_services.osm.schema.OsmHutSource].

    model_config = ConfigDict(coerce_numbers_to_str=True)

    source_name: str = Field("unknown", description="Name of the source (e.g. osm, wikipedia, ...).")

    # hut information
    name: str = Field(..., description="Original hut name.")
    location: LocationEleSchema | None = Field(None, description="Location of the hut.")

    # source information
    source_id: str = Field(..., description="Originial source id of the hut.")
    source_data: TSourceData_co | None = Field(None, description="Source data for this hut.")
    source_properties: TProperties_co | None = Field(None, description="Additinal source data properties.")

    # create information
    version: int = Field(default=0, description="Version of the service when this entry was created.")
    created: datetime = Field(
        default_factory=datetime.now, description="Version of the service when this entry was created."
    )

    def __str__(self) -> str:
        loc = f"({self.location.lon},{self.location.lat})" if self.location is not None else "(no location)"
        return f"<{self.source_name} #{self.source_id} - {self.name} {loc}>"

    @property
    def source_properties_schema(self) -> dict:
        """Returns JSON schema for the 'source_properties' fields.

        Returns:
            JSON schema."""
        if self.source_properties is not None:
            return self.source_properties.model_json_schema(by_alias=True)
        return {}

    def show(
        self,
        source_id: bool = True,
        location: bool = True,
        elevation: bool = True,
        source_name: bool = True,
        version: bool = False,
        created: bool = False,
    ) -> str:
        """Returns a formatted string with the hut information which can be printed.

        Args:
            source_id: Show source ID.
            location:  Show location.
            elevation: Show elevation.
            source_name: Show source name.
            version: Show verions.
            created: Show created date.

        Returns:
            Formatted string.

        """
        out = [f"{self.name}"]
        if source_id:
            out.append(f"  id:        {self.source_id}")
        if location:
            loc = f"{self.location.lon},{self.location.lat}" if self.location is not None else "not set"
            out.append(f"  location:  {loc}")
        if elevation:
            ele = self.location.ele if self.location is not None else "not set"
            out.append(f"  elevation: {ele}")
        if source_name:
            out.append(f"  source:    {self.source_name}")
        if version:
            out.append(f"  version:   {self.version}")
        if created:
            out.append(f"  created:   {self.created}")
        return "\n".join(out)


HutSourceSchema: TypeAlias = BaseHutSourceSchema[SourceDataSchema, SourcePropertiesSchema]
"""Hut source schema, used for typing.
With pydantic `BaseModel` and [`SourcePrpertiesSchema`][hut_services.core.schema.SourcePropertiesSchema]."""

# class HutSourceSchema(BaseHutSourceSchema[BaseModel, SourcePropertiesSchema]):
#    """Hut source schema, used for typing.
#    With pydantic `BaseModel` and [`SourcePrpertiesSchema`][hut_services.core.schema.SourcePropertiesSchema]."""
