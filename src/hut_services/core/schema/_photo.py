from datetime import datetime
import logging
from collections import namedtuple
from typing import Sequence

from pydantic import Field, HttpUrl

from ._base import BaseSchema
from .locale import TranslationSchema

logger = logging.getLogger(__name__)


# PhoneMobile = namedtuple("PhoneMobile", ["phone", "mobile"])


# TODO Lic, Author, Source are general fields not just for photo, mybe subclass for photo?
class LicenseSchema(BaseSchema):
    slug: str
    url: HttpUrl | None = None
    name: str | None = None


class AuthorSchema(BaseSchema):
    name: str
    url: None | HttpUrl = None


class SourceSchema(BaseSchema):
    """
    Photo source information.

    Attributes:
        ident: Identifier or slug of the source.
        name: Name of the source, either person or organization (e.g refuges, wikicommon, sac, ...)
        url: URL of the source.
    """

    ident: str | None = None
    name: str | None = None
    url: HttpUrl | None = None


# TODO: do not use None but just an empty string as default
class PhotoSchema(BaseSchema):
    licenses: list[LicenseSchema]
    caption: TranslationSchema
    author: AuthorSchema | None
    source: SourceSchema | None
    image_url: HttpUrl | None
    width: int | None
    height: int | None
    url: HttpUrl
    date: datetime | None
