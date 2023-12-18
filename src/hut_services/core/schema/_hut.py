import logging
from collections import namedtuple
from enum import Enum
from typing import Annotated, Any

import phonenumbers
from pydantic import BaseModel, Field

from .geo import LocationSchema
from .locale import TranslationSchema

logger = logging.getLogger(__name__)

NaturalInt = Annotated[int, Field(strict=True, ge=0)]

PhoneMobile = namedtuple("PhoneMobile", ["phone", "mobile"])


class ContactSchema(BaseModel):
    """Schema for a contact.

    Attributes:
        name: Contact name (persion or organization), can also be empty.
        email: E-mail address.
        phone: Phone number.
        mobile: Mobule phone number.
        function: Function, e.g. hut warden.
        url: Additional url for this contact (not the hut website).
        address: Address (street, city).
        note: Additional note/information.
        is_active: Contact is active.
        is_public: Show contact public.
    """

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
    def extract_phone_numbers(cls, numbers_string: str, region: str | None = "CH") -> list[str]:
        """Extracts phone numbers from a string and returns them formatted
        with international code.
        Uses the [`phonenumbers`](https://github.com/daviddrysdale/python-phonenumbers) package.

        Args:
            numbers_string: A string with phone numbers in it.
            region: Country code.

        Returns:
            A list with formatted phone numbers.
        """
        phones = []
        _matches = phonenumbers.PhoneNumberMatcher(numbers_string, region=region)
        if not _matches:
            logger.warning(f"Could not match phone CH number: '{numbers_string}'")
        phone_match: phonenumbers.PhoneNumberMatch
        for phone_match in _matches:
            phone_fmt = phonenumbers.format_number(phone_match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            phones.append(phone_fmt)
        return phones

    @classmethod
    def number_to_phone_or_mobile(cls, number: str, region: str | None = None) -> PhoneMobile:
        """Given a phone number it returns it eihter as `phone` or `mobile` number.
        Uses the [`phonenumbers`](https://github.com/daviddrysdale/python-phonenumbers) package.

        Args:
            number: Any phone numbers.
            region: Country code.

        Returns:
            Tuple with `phone` and `mobile` number (`(phone, mobile)`).
        """

        is_mobile = (
            phonenumbers.number_type(phonenumbers.parse(number, region=region)) == phonenumbers.PhoneNumberType.MOBILE
        )
        mobile = number if is_mobile else ""
        phone = number if not is_mobile else ""
        return PhoneMobile(phone=phone, mobile=mobile)


# T = TypeVar("T")
class HutTypeEnum(str, Enum):
    """Enum with hut types."""

    unknown = "unknown"
    campground = "campground"  # possible to camp
    basic_shelter = "basic-shelter"  # only roof, nothing inside
    camping = "camping"  # attended
    bivouac = "bivouac"  # simple bivouac, not much, high up ...
    unattended_hut = "unattended-hut"
    hut = "hut"
    alp = "alp"
    basic_hotel = "basic-hotel"  # simple, not luxiouris hotel, usally with tourist camp
    hostel = "hostel"
    hotel = "hotel"
    special = "special"  # something special, like in a plane or so ...
    restaurant = "restaurant"


class CapacitySchema(BaseModel):
    """Hut capacities.

    Hint:
        For unattended accomodations the `opened` attribute should be used.

    Attributes:
        opened: Capacity when the hut is open
        closed: Capacity when the hut is closed (shelter, winterroom, ...)
    """

    opened: NaturalInt | None = Field(None, description="Capacity when the hut is open")
    closed: NaturalInt | None = Field(None, description="Capacity when the hut is closed (shelter, winterroom, ...)")


class HutSchema(BaseModel):
    """Hut schema.

    Attributes:
        slug: Slug.
        name: Original hut name
        location: Location of the hut
        description: Description.
        notes: Additional public notes to the hut
        owner: Hut owner.
        contacts: Hut contacts.
        url: Hut website.
        comment: Additional private comment to the hut.
        country: Country.
        capacity: Cpacities of the hut.
        is_active: Hut is active.
        is_public: Show hut public.
        hut_type: Hut type (e.g. `unattended-hut`)
        extras: Additional information to the hut as dictionary
    """

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
