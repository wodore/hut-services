import logging
from enum import Enum
from typing import Annotated, Any

import phonenumbers
from pydantic import BaseModel, Field

from .geo import LocationSchema
from .locale import TranslationSchema

logger = logging.getLogger(__name__)

NaturalInt = Annotated[int, Field(strict=True, ge=0)]


class ContactSchema(BaseModel):
    # i18n = TranslationField(fields=("note",))

    name: str = Field("", max_length=70)
    email: str = Field("", max_length=70)
    phone: str = Field("", max_length=30)
    mobile: str = Field("", max_length=30)
    function: str = Field("", max_length=20)
    url: str = Field("", max_length=200)
    address: str = Field("", max_length=200)
    note: TranslationSchema = Field(default_factory=TranslationSchema)
    is_active: bool = True
    is_public: bool = False

    @classmethod
    def format_phone_numbers(cls, number: str, countery: str = "CH") -> list[str]:
        phones = []
        _matches = phonenumbers.PhoneNumberMatcher(number, "CH")
        if not _matches:
            logger.warning(f"Could not match phone CH number: '{number}'")
        phone_match: phonenumbers.PhoneNumberMatch
        for phone_match in _matches:
            phone_fmt = phonenumbers.format_number(phone_match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            phones.append(phone_fmt)
        return phones

    @classmethod
    def number_to_phone_or_mobile(cls, number: str) -> tuple[str, str]:
        """retrns tuple (phone, mobile) depending on 'number'"""
        is_mobile = phonenumbers.number_type(phonenumbers.parse(number)) == phonenumbers.PhoneNumberType.MOBILE
        mobile = number if is_mobile else ""
        phone = number if not is_mobile else ""
        return (phone, mobile)


# T = TypeVar("T")
class HutTypeEnum(str, Enum):
    unknown = "unknown"
    campground = "campground"  # possible to camp
    basic_shelter = "basic-shelter"  # only roof, nothing inside
    camping = "camping"  # attended
    bivouac = "bivouac"  # simple bivouac, not much
    unattended_hut = "unattended-hut"
    hut = "hut"
    alp = "alp"
    basic_hotel = "basic-hotel"  # simple, not luxiouris hotel, usally with tourist camp
    hostel = "hostel"
    hotel = "hotel"
    special = "special"
    restaurant = "restaurant"


class CapacitySchema(BaseModel):
    opened: NaturalInt | None = Field(None, description="Capacity when the hut is open")
    closed: NaturalInt | None = Field(None, description="Capacity when the hut is cloes (shelter, winterroom, ...)")


class HutSchema(BaseModel):
    slug: str | None = None
    name: TranslationSchema = Field(..., description="Original hut name.")
    location: LocationSchema = Field(..., description="Location of the hut.")

    description: TranslationSchema = Field(default_factory=TranslationSchema)
    notes: list[TranslationSchema] = Field(..., description="Additional notes to the hut.")
    owner: str | None = Field(None, max_length=100)
    contacts: list[ContactSchema] = Field(default_factory=list)
    url: str = Field("", max_length=200)
    comment: str = Field("", max_length=2000)

    # photos:        List[Photo] = Field(default_factory=list, sa_column=Column(PydanticType(List[Photo])))

    country: str | None = Field("ch", max_length=2, min_length=2)
    capacity: CapacitySchema

    # infrastructure:       dict = Field(default_factory=dict, sa_column=Column(JSON)) # TODO, better name. Maybe use infra and service separated, external table
    # access:             Access = Field(default_factory=Access, sa_column=Access.get_sa_column())

    is_active: bool = Field(default=True)
    is_public: bool = Field(default=True)

    # monthly:            Monthly = Field(default_factory=Monthly, sa_column=Monthly.get_sa_column())
    hut_type: HutTypeEnum = Field(alias="type")

    extras: dict[str, Any] = Field(default_factory=dict, description="Additional information.")

    def __str__(self) -> str:
        slug = self.slug if self.slug else self.name.i18n.lower().replace(" ", "-")[:8]
        return f"<{slug} {self.name.i18n} ({self.location.lon},{self.location.lat})>"

    # def show(
    #    self,
    #    source_id: bool = True,
    #    location: bool = True,
    #    elevation: bool = True,
    #    source_name: bool = True,
    #    version: bool = False,
    #    created: bool = False,
    # ) -> str:
    #    """Returns a formated string with the hut information which can be printed."""
    #    out = [f"{self.name}"]
    #    if source_id:
    #        out.append(f"  id:        {self.source_id}")
    #    if location:
    #        out.append(f"  location:  {self.location.lon},{self.location.lat}")
    #    if elevation:
    #        out.append(f"  elevation: {self.location.ele}")
    #    if source_name:
    #        out.append(f"  source:    {self.source_name}")
    #    if version:
    #        out.append(f"  version:   {self.version}")
    #    if created:
    #        out.append(f"  created:   {self.created}")
    #    return "\n".join(out)
