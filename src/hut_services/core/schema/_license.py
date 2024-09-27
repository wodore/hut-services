import logging

from pydantic import Field
from pydantic_string_url import HttpUrl

from ._base import BaseSchema

logger = logging.getLogger(__name__)


class LicenseSchema(BaseSchema):
    """
    License information.

    Attributes:
        slug: Identifier or slug of the license (e.g. by-sa, cc-0, ...).
        url: URL of the license.
        name: Fullname of the license.
    """

    slug: str
    url: HttpUrl | None = None
    name: str = Field("", max_length=300)


class AuthorSchema(BaseSchema):
    """
    Author information.

    Attributes:
        name: Name of the author.
        url: URL of the author.
    """

    name: str
    url: None | HttpUrl = None


class SourceSchema(BaseSchema):
    """
    Source information.

    Attributes:
        ident: Identifier or slug of the source.
        name: Name of the source, either person or organization (e.g refuges, wikicommon, sac, ...)
        url: URL of the source.
    """

    ident: str = Field("", max_length=300)
    name: str = Field("", max_length=300)
    url: HttpUrl | None = None
