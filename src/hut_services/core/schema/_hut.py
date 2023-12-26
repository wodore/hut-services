from typing import Any, Mapping, Sequence

from pydantic import Field, model_validator
from slugify import slugify

from ._base import BaseSchema
from ._contact import ContactSchema
from ._hut_fields import CapacitySchema, HutTypeSchema, OpenMonthlySchema, OwnerSchema, PhotoSchema
from .geo import LocationEleSchema
from .locale import TranslationSchema

# import logging
# logger = logging.getLogger(__name__)


class HutSchema(BaseSchema):
    """Hut schema.

    Attributes:
        slug: Hut slug, if empty it is replaced by slugified `name`.
        name: Original hut name.
        location: Location of the hut.
        description: Description.
        notes: Additional public notes to the hut.
        owner: Hut owner.
        url: Hut website.
        contacts: Hut contacts.
        country_code: Country.
        comment: Additional private comment to the hut.
        capacity: Cpacities of the hut.
        type: Hut type (e.g. `selfhut`).
        photos: Hut photos.
        open_monthly: Monthly value if open, closed or partially open.
        is_active: Hut is active.
        is_public: Show hut public.
        extras: Additional information to the hut as dictionary
    """

    slug: str = Field("", max_length=50)
    name: TranslationSchema = Field(..., description="Original hut name.")
    location: LocationEleSchema = Field(..., description="Location of the hut with optional elevation.")

    description: TranslationSchema = Field(default_factory=TranslationSchema)
    notes: Sequence[TranslationSchema] = Field(..., description="Additional notes to the hut.")
    owner: OwnerSchema | None = Field(None)
    url: str = Field("", max_length=200)
    contacts: Sequence[ContactSchema] = Field(default_factory=list)
    country_code: str | None = Field(None, max_length=2, min_length=2)
    comment: str = Field("", max_length=20000, description="Additional private comment, e.g for review.")
    capacity: CapacitySchema
    hut_type: HutTypeSchema = Field(..., alias="type")
    photos: list[PhotoSchema] = Field(default_factory=list)
    open_monthly: OpenMonthlySchema
    is_active: bool = Field(default=True)
    is_public: bool = Field(default=True)
    extras: Mapping[str, Any] = Field(default_factory=dict, description="Additional information as dictionary.")

    # infrastructure:       dict = Field(default_factory=dict, sa_column=Column(JSON)) # TODO, better name. Maybe use infra and service separated, external table
    # access:             Access = Field(default_factory=Access, sa_column=Access.get_sa_column())

    def __str__(self) -> str:
        slug = self.slug if self.slug else self.name.i18n.lower().replace(" ", "-")[:8]
        return f"<{slug} {self.name.i18n} ({self.location.lon},{self.location.lat})>"

    @model_validator(mode="after")
    def add_slug(self) -> "HutSchema":
        if not self.slug:
            self.slug = slugify(self.name.i18n, max_length=50, word_boundary=True)
        return self
