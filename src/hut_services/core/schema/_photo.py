from datetime import datetime

from pydantic import Field
from pydantic_string_url import HttpUrl

from ._base import BaseSchema
from ._license import AuthorSchema, LicenseSchema, SourceSchema
from .locale import TranslationSchema


class PhotoSchema(BaseSchema):
    """Schema for a hut photo."""

    licenses: list[LicenseSchema]
    caption: TranslationSchema = Field(default_factory=TranslationSchema)
    source: SourceSchema | None
    author: AuthorSchema | None
    comment: str = Field("", max_length=20000, description="Additional private comment, e.g for review.")
    raw_url: HttpUrl = Field(..., description="Url to the raw image, this can be used to download or embed the image.")
    width: int = Field(..., description="Image width in pixels.")
    height: int = Field(..., description="Image height in pixels.")
    url: HttpUrl = Field(
        ...,
        description="Url to the image on the side, this should not be used to include it direclty, rather to just link to it.",
    )
    capture_date: datetime | None
    tags: list[str] | None = None
