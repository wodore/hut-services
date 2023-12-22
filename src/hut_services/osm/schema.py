import logging
import textwrap
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, computed_field

from hut_services.core.schema import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    CapacitySchema,
    ContactSchema,
    OwnerSchema,
    SourcePropertiesSchema,
)
from hut_services.core.schema.geo import LocationSchema
from hut_services.core.schema.geo.types import Elevation, Latitude, Longitude
from hut_services.core.schema.locale import TranslationSchema

from .exceptions import OSMCoordinatesError
from .utils import guess_hut_type

logger = logging.getLogger(__name__)


class OSMTags(BaseModel):
    """Open street map tags."""

    tourism: Literal["alpine_hut", "wilderness_hut"]
    wikidata: Optional[str] = None

    name: str
    operator: Optional[str] = None
    email: Optional[str] = None
    contact_email: Optional[str] = Field(None, alias="contact:field")
    phone: Optional[str] = None
    contact_phone: Optional[str] = Field(None, alias="contact:phone")
    website: Optional[str] = None
    contact_website: Optional[str] = Field(None, alias="contact:website")
    note: Optional[str] = None

    bed: Optional[str] = None
    beds: Optional[str] = None
    capacity: Optional[str] = None
    access: Optional[str] = None
    fireplace: Optional[str] = None
    wall: Optional[str] = None
    amenity: Optional[str] = None
    shelter_type: Optional[str] = None
    winter_room: Optional[str] = None
    reservation: Optional[str] = None

    # ele: Optional[Elevation]
    ele: Optional[Elevation] = None


class OsmHutSchema(BaseModel):
    """Open street map schema."""

    osm_type: Literal["node", "way", "area"] | None = None
    osm_id: int = Field(..., alias="id")
    lat: Latitude | None = None
    lon: Longitude | None = None
    center_lat: Latitude | None = None
    center_lon: Longitude | None = None
    tags: OSMTags

    def get_id(self) -> str:
        """Get open street map `id`."""
        return str(self.osm_id)

    def get_name(self) -> str:
        """Get open street map hut name."""
        return self.tags.name

    def get_location(self) -> LocationSchema:
        """Get open street map location."""
        if self.lat and self.lon:
            return LocationSchema(lat=self.lat, lon=self.lon, ele=self.tags.ele)
        elif self.center_lat and self.center_lon:
            return LocationSchema(lat=self.center_lat, lon=self.center_lon, ele=self.tags.ele)
        else:
            raise OSMCoordinatesError(self.osm_id, self.get_name())


class OsmProperties(SourcePropertiesSchema):
    osm_type: Literal["node", "way", "area"] = Field(..., description="osm object type: node, way, or area")


class OsmHutSource(BaseHutSourceSchema[OsmHutSchema, OsmProperties]):
    source_name: str = "osm"


class OsmHut0Convert(BaseHutConverterSchema[OsmHutSchema]):
    @property
    def _tags(self) -> OSMTags:
        return self.source.tags

    @computed_field  # type: ignore[misc]
    @property
    def slug(self) -> str:
        return f"osm-{self.source.get_id()}"

    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(de=self._tags.name[:69])

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema()

    @computed_field  # type: ignore[misc]
    @property
    def comment(self) -> str:
        note = ""
        if self._tags.note:
            note = f"OSM note: {self._tags.note}\n"
        return note

    @computed_field  # type: ignore[misc]
    @property
    def extras(self) -> dict[str, Any]:
        extras = {}
        if self._tags.wikidata:
            extras["wikidata"] = self._tags.wikidata
        return extras

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        url = ""
        if self._tags.website:
            url = self._tags.website
        elif self._tags.contact_website:
            url = self._tags.contact_website
        if len(url) > 200:
            url = ""
        return url

    @property
    def _capacity_opened(self) -> Optional[int]:
        tags = self._tags
        cap: int | None = None
        cap_str: str | None = None
        if tags.capacity:
            cap_str = tags.capacity
        elif tags.beds:
            cap_str = tags.beds
        elif tags.bed:
            cap_str = tags.bed
        try:
            if cap_str is not None:
                cap = int(cap_str)
        except ValueError:
            cap = None
        return cap

    @property
    def _capacity_closed(self) -> Optional[int]:
        if self._tags.winter_room:
            try:
                return int(self._tags.winter_room)  # capacity in tag
            except ValueError:
                pass
        # if self._tags.tourism == "wilderness_hut":
        #    return self._capacity_opened
        return None

    @computed_field  # type: ignore[misc]
    @property
    def capacity(self) -> CapacitySchema:
        return CapacitySchema(opened=self._capacity_opened, closed=self._capacity_closed)

    @computed_field(alias="type")  # type: ignore[misc]
    @property
    def hut_type(self) -> str:
        _orgs = ""
        if self._tags.operator:
            _orgs = "sac" if "sac" in self._tags.operator else ""
        return guess_hut_type(
            name=self.name.i18n or "",
            capacity=self.capacity.opened,
            capacity_shelter=self.capacity.closed,
            elevation=self.location.ele,
            organization=_orgs,
            osm_tag=self._tags.tourism,
        )

    @computed_field  # type: ignore[misc]
    @property
    def owner(self) -> OwnerSchema | None:
        name = self._tags.operator or ""
        comment = ""
        if len(name) > 60:
            comment = f"Full name: {name}"
            name = textwrap.shorten(name, width=57, placeholder="...")
        if name:
            return OwnerSchema(name=name, comment=comment)
        return None

    @computed_field  # type: ignore[misc]
    @property
    def is_active(self) -> bool:
        return True

    @computed_field  # type: ignore[misc]
    @property
    def is_public(self) -> bool:
        if self._tags.access:
            return self._tags.access in ["yes", "public", "customers", "permissive"]
        return True

    @property
    def _email(self) -> str:
        if self._tags.email:
            return self._tags.email.strip()
        elif self._tags.contact_email:
            return self._tags.contact_email.strip()
        return ""

    @property
    def _phones(self) -> list[str]:
        phone = None
        if self._tags.phone:
            phone = self._tags.phone
        elif self._tags.contact_phone:
            phone = self._tags.contact_phone
        phones = []
        if phone:
            phones += ContactSchema.extract_phone_numbers(phone, region="CH")
        return phones

    @computed_field  # type: ignore[misc]
    @property
    def contacts(self) -> list[ContactSchema]:
        contacts = []
        emails = self._email
        for phone in self._phones:
            phone, mobile = ContactSchema.number_to_phone_or_mobile(phone, region="CH", formatted=True)
            contacts.append(
                ContactSchema(
                    phone=phone, email=emails.strip(), mobile=mobile, name="", function="contact", is_public=True
                )
            )
            if emails:
                emails = ""
        if emails:
            for email in emails.split(";"):
                contacts.append(ContactSchema(email=email.strip(), function="contact", is_public=True))
        return contacts
