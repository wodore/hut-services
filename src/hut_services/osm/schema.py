import logging
import textwrap
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

from hut_services import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    CapacitySchema,
    ContactSchema,
    HutTypeEnum,
    HutTypeSchema,
    LocationEleSchema,
    OwnerSchema,
    PhotoSchema,
    SourceDataSchema,
    SourcePropertiesSchema,
    TranslationSchema,
)
from hut_services.core.schema.geo.types import Elevation, Latitude, Longitude

from ..core.guess import guess_hut_type

# from hut_services.wikidata import WikidataService
# from hut_services.wikidata.service import WikidataEntity  # , wikidata_service
from .exceptions import OSMCoordinatesError

logger = logging.getLogger(__name__)


class OSMTags(BaseModel):
    """Open street map tags."""

    tourism: Literal["alpine_hut", "wilderness_hut"]
    wikidata: str | None = None

    name: str
    operator: str | None = None
    email: str | None = None
    contact_email: str | None = Field(None, alias="contact:field")
    phone: str | None = None
    contact_phone: str | None = Field(None, alias="contact:phone")
    website: str | None = None
    contact_website: str | None = Field(None, alias="contact:website")
    note: str | None = None

    bed: str | None = None
    beds: str | None = None
    capacity: str | None = None
    access: str | None = None
    fireplace: str | None = None
    wall: str | None = None
    amenity: str | None = None
    shelter_type: str | None = None
    winter_room: str | None = None
    reservation: str | None = None

    # ele: Optional[Elevation]
    ele: Elevation | None = None


class OSMTagsOptional(OSMTags):
    """Open street map tags, all optional."""

    tourism: str | None = None  # type: ignore[assignment]
    name: str | None = None  # type: ignore[assignment]
    ele: float | str | None = None  # type: ignore[assignment]


class OsmHutSchema(SourceDataSchema):
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

    def get_location(self) -> LocationEleSchema:
        """Get open street map location."""
        lat: float | None
        lon: float | None
        # coordinate fixes
        if self.osm_id == 1386596359:  # Winteregghütte
            lat, lon = 46.46039, 7.64995
        elif self.osm_id == 505804029:  # Ostegg
            lat, lon = 46.60037, 8.04120
        else:
            lat, lon = self.lat, self.lon
        if lat and lon:
            return LocationEleSchema(lat=lat, lon=lon, ele=self.tags.ele)
        elif self.center_lat and self.center_lon:
            return LocationEleSchema(lat=self.center_lat, lon=self.center_lon, ele=self.tags.ele)
        else:
            raise OSMCoordinatesError(self.osm_id, self.get_name())


class OsmProperties(SourcePropertiesSchema):
    osm_type: Literal["node", "way", "area"] = Field(..., description="osm object type: node, way, or area")


class OsmHutSource(BaseHutSourceSchema[OsmHutSchema, OsmProperties]):
    version: int = 0
    source_name: str = "osm"


class OsmHut0Convert(BaseHutConverterSchema[OsmHutSchema]):
    include_photos: bool = False

    @property
    def _tags(self) -> OSMTags:
        return self.source_data.tags

    # implemented in base
    # @computed_field  # type: ignore[prop-decorator]
    # @property
    # def slug(self) -> str:
    #    return f"osm-{self.source.get_id()}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(de=self._tags.name[:69])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_name(self) -> str:
        return "osm"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema()

    @computed_field  # type: ignore[prop-decorator]
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

    @computed_field  # type: ignore[prop-decorator]
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

    ## Contact
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

    @computed_field  # type: ignore[prop-decorator]
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def comment(self) -> str:
        note = ""
        if self._tags.note:
            note = f"OSM note: {self._tags.note}\n"
        return note

    @property
    def _capacity_opened(self) -> int | None:
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
    def _capacity_closed(self) -> int | None:
        if self._tags.winter_room:
            number = None
            try:
                number = int(self._tags.winter_room)  # capacity in tag
            except ValueError:
                return None
            return number
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capacity(self) -> CapacitySchema:
        closed = self._capacity_closed
        if closed == self._capacity_opened:
            closed = None
        return CapacitySchema(open=self._capacity_opened, closed=closed)

    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def hut_type(self) -> HutTypeSchema:
        capacity = CapacitySchema(open=self._capacity_opened, closed=self._capacity_closed)
        hut_types = guess_hut_type(
            name=self.name.i18n or "",
            capacity=capacity,
            elevation=self.location.ele,
            operator="sac" if self._tags.operator and "sac" in self._tags.operator else None,
            osm_tag=self._tags.tourism,
        )
        if hut_types.if_open == HutTypeEnum.hut and capacity.if_open in [0, None]:
            hut_types.if_open = HutTypeEnum.unknown
            hut_types.if_closed = None
        return hut_types

    @property
    def wikidata_entity(self) -> None:
        # if self._tags.wikidata and self.get_wikidata_photos:
        #    return wikidata_service.get_entity(self._tags.wikidata)
        return None

    @computed_field()  # type: ignore[prop-decorator]
    @property
    def photos(self) -> list[PhotoSchema]:
        """Not supported for osm data, use wikidata isntead which are based on the osm data."""
        if self.wikidata_entity is not None and self.include_photos:
            return self.wikidata_entity.get_photos()
        return []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_active(self) -> bool:
        return True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_public(self) -> bool:
        if self._tags.access:
            return self._tags.access in ["yes", "public", "customers", "permissive"]
        return True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def extras(self) -> dict[str, Any]:
        extras = {}
        if self._tags.wikidata:
            extras["wikidata"] = self._tags.wikidata
        return extras
