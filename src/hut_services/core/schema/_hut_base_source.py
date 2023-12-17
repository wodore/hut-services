from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from .geo import LocationSchema

DataT = TypeVar("DataT", bound=BaseModel)
PropertiesT = TypeVar("PropertiesT", bound=BaseModel)


class BaseHutSourceSchema(BaseModel, Generic[DataT, PropertiesT]):
    source_name: str = Field(..., description="Name of the source (e.g. osm, wikipedia, ...).")

    # hut information
    name: str = Field(..., description="Original hut name.")
    location: LocationSchema = Field(..., description="Location of the hut.")

    # source information
    source_id: str = Field(..., description="Originial source id of the hut.")
    source_data: DataT | None = Field(None, description="Source data for this hut.")
    source_properties: PropertiesT | None = Field(None, description="Additinal source data properties.")

    # create information
    version: int = Field(default=0, description="Version of the service when this entry was created.")
    created: datetime = Field(
        default_factory=datetime.now, description="Version of the service when this entry was created."
    )

    def __str__(self) -> str:
        return f"<{self.source_name} #{self.source_id} - {self.name} ({self.location.lon},{self.location.lat})>"

    @property
    def source_properties_schema(self) -> dict:
        """Returns JSON schema for the 'source_properties' fields."""
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
        """Returns a formated string with the hut information which can be printed."""
        out = [f"{self.name}"]
        if source_id:
            out.append(f"  id:        {self.source_id}")
        if location:
            out.append(f"  location:  {self.location.lon},{self.location.lat}")
        if elevation:
            out.append(f"  elevation: {self.location.ele}")
        if source_name:
            out.append(f"  source:    {self.source_name}")
        if version:
            out.append(f"  version:   {self.version}")
        if created:
            out.append(f"  created:   {self.created}")
        return "\n".join(out)
