import logging
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, computed_field

from hut_services import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    LocationEleSchema,
    PhotoSchema,
    SourcePropertiesSchema,
    TranslationSchema,
)
from hut_services.core.schema.geo.types import Elevation, Latitude, Longitude

# from hut_services.wikidata import WikidataService
# from hut_services.wikidata.service import WikidataEntity  # , wikidata_service


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
    #    @property
    #    def _tags(self) -> OSMTags:
    #        return self.source.tags
    #
    @computed_field  # type: ignore[misc]
    @property
    def slug(self) -> str:
        return f"wikidata-{self.source.get_id()}"

    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(de=self.source.get_name())

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema()

    # @computed_field  # type: ignore[misc]
    # @property
    # def owner(self) -> OwnerSchema | None:
    #    name = self._tags.operator or ""
    #    comment = ""
    #    if len(name) > 60:
    #        comment = f"Full name: {name}"
    #        name = textwrap.shorten(name, width=57, placeholder="...")
    #    if name:
    #        return OwnerSchema(name=name, comment=comment)
    #    return None

    # @computed_field  # type: ignore[misc]
    # @property
    # def url(self) -> str:
    #    url = ""
    #    if self._tags.website:
    #        url = self._tags.website
    #    elif self._tags.contact_website:
    #        url = self._tags.contact_website
    #    if len(url) > 200:
    #        url = ""
    #    return url

    ### Contact
    # @property
    # def _email(self) -> str:
    #    if self._tags.email:
    #        return self._tags.email.strip()
    #    elif self._tags.contact_email:
    #        return self._tags.contact_email.strip()
    #    return ""

    # @property
    # def _phones(self) -> list[str]:
    #    phone = None
    #    if self._tags.phone:
    #        phone = self._tags.phone
    #    elif self._tags.contact_phone:
    #        phone = self._tags.contact_phone
    #    phones = []
    #    if phone:
    #        phones += ContactSchema.extract_phone_numbers(phone, region="CH")
    #    return phones

    # @computed_field  # type: ignore[misc]
    # @property
    # def contacts(self) -> list[ContactSchema]:
    #    contacts = []
    #    emails = self._email
    #    for phone in self._phones:
    #        phone, mobile = ContactSchema.number_to_phone_or_mobile(phone, region="CH", formatted=True)
    #        contacts.append(
    #            ContactSchema(
    #                phone=phone, email=emails.strip(), mobile=mobile, name="", function="contact", is_public=True
    #            )
    #        )
    #        if emails:
    #            emails = ""
    #    if emails:
    #        for email in emails.split(";"):
    #            contacts.append(ContactSchema(email=email.strip(), function="contact", is_public=True))
    #    return contacts

    # @computed_field  # type: ignore[misc]
    # @property
    # def comment(self) -> str:
    #    note = ""
    #    if self._tags.note:
    #        note = f"OSM note: {self._tags.note}\n"
    #    return note

    # @property
    # def _capacity_opened(self) -> Optional[int]:
    #    tags = self._tags
    #    cap: int | None = None
    #    cap_str: str | None = None
    #    if tags.capacity:
    #        cap_str = tags.capacity
    #    elif tags.beds:
    #        cap_str = tags.beds
    #    elif tags.bed:
    #        cap_str = tags.bed
    #    try:
    #        if cap_str is not None:
    #            cap = int(cap_str)
    #    except ValueError:
    #        cap = None
    #    return cap

    # @property
    # def _capacity_closed(self) -> Optional[int]:
    #    if self._tags.winter_room:
    #        number = None
    #        try:
    #            number = int(self._tags.winter_room)  # capacity in tag
    #        except ValueError:
    #            return None
    #        if number != self._capacity_opened:
    #            return number
    #    # if self._tags.tourism == "wilderness_hut":
    #    #    return self._capacity_opened
    #    return None

    # @computed_field  # type: ignore[misc]
    # @property
    # def capacity(self) -> CapacitySchema:
    #    return CapacitySchema(open=self._capacity_opened, close=self._capacity_closed)

    # @property
    # def _hut_type_open(self) -> HutTypeEnum:
    #    _orgs = ""
    #    if self._tags.operator:
    #        _orgs = "sac" if "sac" in self._tags.operator else ""
    #    return guess_hut_type(
    #        name=self.name.i18n or "",
    #        capacity=self.capacity.if_open,
    #        capacity_shelter=self.capacity.if_closed,
    #        elevation=self.location.ele,
    #        organization=_orgs,
    #        osm_tag=self._tags.tourism,
    #    )

    # @property
    # def _hut_type_closed(self) -> HutTypeEnum | None:
    #    if self._hut_type_open == "hut" and self.capacity.if_closed:
    #        if (self.location.ele or 0) < 2500:
    #            return HutTypeEnum.unattended_hut
    #        else:
    #            return HutTypeEnum.bivouac
    #    return None

    # @computed_field(alias="type")  # type: ignore[misc]
    # @property
    # def hut_type(self) -> HutTypeSchema:
    #    return HutTypeSchema(open=self._hut_type_open, close=self._hut_type_closed)

    # @property
    # def wikidata_entity(self) -> None:
    #    # if self._tags.wikidata and self.get_wikidata_photos:
    #    #    return wikidata_service.get_entity(self._tags.wikidata)
    #    return None

    @computed_field()  # type: ignore[misc]
    @property
    def photos(self) -> list[PhotoSchema]:
        return self.source.photos
        # if self.wikidata_entity is not None:
        #    return self.wikidata_entity.get_photos()
        # return []

    # @computed_field  # type: ignore[misc]
    # @property
    # def is_active(self) -> bool:
    #    return True

    # @computed_field  # type: ignore[misc]
    # @property
    # def is_public(self) -> bool:
    #    if self._tags.access:
    #        return self._tags.access in ["yes", "public", "customers", "permissive"]
    #    return True

    # @computed_field  # type: ignore[misc]
    # @property
    # def extras(self) -> dict[str, Any]:
    #    extras = {}
    #    if self._tags.wikidata:
    #        extras["wikidata"] = self._tags.wikidata
    #    return extras