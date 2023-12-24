import logging
from enum import Enum
from typing import Annotated

from pydantic import Field, model_validator
from slugify import slugify

from ._base import BaseSchema
from ._contact import ContactSchema
from .locale import TranslationSchema

logger = logging.getLogger(__name__)

NaturalInt = Annotated[int, Field(strict=True, ge=0)]


class OwnerSchema(BaseSchema):
    """Schema for the owner.

    Attributes:
        slug: Owner slug, if empty it is replaced by slugified `name`.
        name: Owner name, required.
        url: Owners URL (not the hut website).
        note: Additonal (public) note to the owner.
        comment: Private comment to the owner.
        contacts: Contacts used for the owner.
    """

    slug: str = Field("", max_length=50)
    name: str = Field(..., max_length=100)
    url: str = Field("", max_length=200)
    note: TranslationSchema = Field(default_factory=TranslationSchema)
    comment: str = ""
    contacts: ContactSchema | None = None

    @model_validator(mode="after")
    def add_slug(self) -> "OwnerSchema":
        if not self.slug:
            self.slug = slugify(self.name, max_length=50, word_boundary=True)
        return self


# T = TypeVar("T")
class HutTypeEnum(str, Enum):
    """Enum with hut types."""

    unknown = "unknown"
    closed = "closed"
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


class CapacitySchema(BaseSchema):
    """Hut capacities.

    Hint:
        For unattended accomodations the `opened` attribute should be used.

    Attributes:
        open:   Capacity when the hut is open
        closed: Capacity when the hut is closed (shelter, winterroom, ...)
    """

    if_open: NaturalInt | None = Field(None, alias="open", description="Capacity when the hut is open")
    if_closed: NaturalInt | None = Field(
        None, alias="close", description="Capacity when the hut is closed (shelter, winterroom, ...)"
    )


class HutTypeSchema(BaseSchema):
    """Hut type schema.

    Defines the type of the hut if it is open and closed. E.g. a hut can be a 'unattended-hut' if it is closed.
    If a hut is always open do not add anything to `closed`. If it is specifcally closed, e.g. during winter ass `'closed'`.

    Attributes:
        open:   Type when the hut is open
        closed: Type when the hut is closed (bivouac, unattended-hut, closed, ...)
    """

    if_open: HutTypeEnum = Field(HutTypeEnum.unknown, alias="open", description="Type when the hut is open")
    if_close: HutTypeEnum | None = Field(
        None, alias="close", description="Type when the hut is closed (bivouac, unattended-hut, closed, ...)"
    )


class PhotoSchema(BaseSchema):
    """Photo schema.

    Attributes:
        url: Link to photo.
        caption: Caption of the photo.
        copyright: Copyright text, e.g. Hans Muster, DAV.
        is_public: Show image to the public.
    """

    attribution: str = Field("", description="Attribution, resp. copyright information as markdown text")
    url: str
    thumb: str = Field("", description="Url to thumbnail (around 400px).")
    caption: TranslationSchema | None = Field(None, description="Original hut name.")
    comment: str = Field("", max_length=20000, description="Additional private comment, e.g for review.")
    is_public: bool = Field(default=True)


class OpenMonthlyEnum(str, Enum):
    """Enum with open values."""

    yes = "yes"
    partial = "partial"
    closed = "closed"
    unknown = "unknown"


class OpenMonthlySchema(BaseSchema):
    """Shows for every month if it is usally, open, partially open or closed.

    Attributes:
        url: URL which shows if it is open or not.
        month_mm (OpenMonthly): Month (starting with 01)."""

    url: str = Field("", description="URL which shows if it is open or not.")
    month_01: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_02: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_03: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_04: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_05: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_06: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_07: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_08: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_09: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_10: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_11: OpenMonthlyEnum = OpenMonthlyEnum.unknown
    month_12: OpenMonthlyEnum = OpenMonthlyEnum.unknown

    def __getitem__(self, month: int) -> OpenMonthlyEnum:
        if month > 0 and month <= 12:
            return getattr(self, f"month_{month:02d}")  # type: ignore[no-any-return]
        else:
            raise IndexError

    def __setitem__(self, month: int, value: OpenMonthlyEnum) -> None:
        if month > 0 and month <= 12:
            setattr(self, f"month_{month:02d}", value)
        else:
            raise IndexError

    def set_month(self, month: int, value: OpenMonthlyEnum) -> None:
        if month > 0 and month <= 12:
            setattr(self, f"month_{month:02d}", value)
        else:
            raise IndexError
