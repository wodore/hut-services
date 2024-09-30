#!/usr/bin/env python
# from functools import lru_cache
import logging
import re
import typing as t
from datetime import datetime
from typing import Any, cast
from urllib.parse import quote, urlparse

import defusedxml.ElementTree
import requests

# from typing import Any, Literal, Mapping
from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError
from pydantic_string_url import HttpUrl
from rich import print

from hut_services import (
    AuthorSchema,
    LicenseSchema,
    PhotoSchema,
    SourceSchema,
    TranslationSchema,
    file_cache,
)
from hut_services.core.schema import HutSchema
from hut_services.core.schema.geo import BBox

if __name__ == "__main__":  # only for testing
    from icecream import ic  # type: ignore[import-untyped] # noqa: F401, RUF100 , PGH003
    from rich import print as rprint  # noqa: F401, RUF100
    from rich.traceback import install

    install(show_locals=False)


logger = logging.getLogger(__name__)


def _parse_href_html_field(html: str | None) -> tuple[str, HttpUrl | None]:
    """Parse an HTML field to extract plain text and URL (if present)."""
    if not html:
        return "", None
    soup = BeautifulSoup(html, "html.parser")
    if soup.a:
        name = soup.a.text or ""
        url = soup.a.get("href")
        if isinstance(url, list):
            url = url[0]
        url_cast = t.cast(HttpUrl, url) if url is not None else None
        return name, url_cast
    else:
        return html.strip(), None


def _parse_time_html_field(html: str | None) -> datetime | None:
    """
    Parse an HTML field to extract a datetime object.

    Args:
        html: The HTML field to parse.

    Returns:
        The extracted datetime object, or None if parsing fails.
    """
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    time_tag = soup.find("time")
    if time_tag and isinstance(time_tag, Tag):
        datetime_str = str(time_tag.get("datetime"))
        try:
            return datetime.strptime(datetime_str, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Handle other possible date formats or raise an error
                return None
    return None


def _extract_hostname(url: str) -> str:
    """Extract the hostname from a full URL."""
    parsed_url = urlparse(url)
    return parsed_url.hostname if parsed_url.hostname else url


def _resize_image_url(url: str, max_dimension: int) -> str:
    """Resize the image URL if width or height exceeds max_dimension."""
    filename = url.split("/")[-1]
    return (url + f"/{max_dimension}px-{filename}").replace("commons/", "commons/thumb/")


@file_cache()
def _wikicommon_api_call(
    filename: str, api_url: str = "https://magnus-toolserver.toolforge.org/commonsapi.php"
) -> bytes | None:
    """Fetch image information from Magnus Toolserver API and return structured data using Pydantic."""
    api_url_image = f"{api_url}?image={filename}"
    response = requests.get(api_url_image, timeout=20)

    if response.status_code != 200:
        err_msg = f"Error fetching data from Magnus Toolserver: {response.status_code}"
        raise Exception(err_msg)  # noqa: TRY002
    return response.content if isinstance(response.content, bytes) else None


def get_wikicommon_photo_info(
    filename: str, api_url: str = "https://magnus-toolserver.toolforge.org/commonsapi.php", max_dimension: int = 3000
) -> PhotoSchema:
    """Fetch image information from Magnus Toolserver API and return structured data using Pydantic."""
    content = _wikicommon_api_call(filename, api_url)

    # Parse XML response
    root = defusedxml.ElementTree.fromstring(content)

    # Extract fields from XML
    file_info = root.find("file")

    def file_info_find(name: str, default: str | None = None, elem: Any = None) -> str | None:
        elem = file_info if elem is None else elem
        if elem is not None:
            return elem.find(name).text if elem.find(name) is not None else default
        return default

    assert file_info is not None  # noqa: S101

    # Image URL and dimensions
    image_url = file_info_find("urls/file")
    title = file_info_find("title")
    width = int(cast(str, file_info_find("width")))
    height = int(cast(str, file_info_find("height")))
    img_date = _parse_time_html_field(cast(str, file_info_find("date")))

    wikicommons_url = f"https://commons.wikimedia.org/wiki/{quote(title or '')}"
    # Resize the image URL if width or height is greater than max_dimension
    if image_url and width and height and (width > max_dimension or height > max_dimension):
        image_url = _resize_image_url(image_url, max_dimension)
        # update height
        orig_height = height
        orig_width = width
        height = max_dimension if orig_height > orig_width else round(orig_height / orig_width * max_dimension)
        width = max_dimension if orig_width > orig_height else round(orig_width / orig_height * max_dimension)
    # License information
    license_elems = root.findall("licenses/license")
    license_name = "No license available"
    license_slug = "missing"
    license_info_url: HttpUrl | None = None
    licenses = []
    for license_elem in license_elems:
        license_name = cast(
            str, file_info_find("name", file_info_find("full_name", "missing", license_elem), license_elem)
        )
        license_name = license_name.replace("migrated", "").strip(" -")
        license_slug = license_name.lower()
        license_info_url = cast(HttpUrl | None, file_info_find("license_info_url", None, license_elem))
        if "cc" in license_slug.lower():
            license_slug = license_slug.split(",")[0].strip()
        licenses.append(LicenseSchema(slug=license_slug, url=license_info_url, name=license_name))

    # Captions only
    captions = TranslationSchema()
    captions_elem = root.find("description")
    if captions_elem is not None:
        for lang_elem in captions_elem.findall("language"):
            lang_code = lang_elem.get("code")
            caption = lang_elem.text.strip() if lang_elem.text else ""
            if lang_code in ["en", "de", "it", "fr"]:
                setattr(captions, lang_code, caption)

    # Author and Source
    author_raw = file_info_find("author", "")
    source_raw = file_info_find("source", wikicommons_url)

    # Parse author and source
    author_name, author_url = _parse_href_html_field(author_raw)
    source_name, source_url = _parse_href_html_field(source_raw)

    # Handle 'int-own-work' source
    source_ident = title
    if "int-own-work" in source_name:
        source_url = cast(HttpUrl, wikicommons_url)
        source_name = "wikicommons"
    if "camptocamp.org" in source_name.lower():
        source_name = "camptocamp"
        match = re.search(r"\d{3,}", cast(str, source_url))
        source_ident = match.group() if match else source_ident
        match = re.search(r"http:.*/\d{3,}", cast(str, source_url))
        source_url = cast(HttpUrl, match.group()) if match else source_url
    if "refuges.info" in source_name.lower():
        source_name = "refuges.info"
        match = re.search(r"(\d{3,})-originale", cast(str, source_url))
        if match:
            source_ident = match.groups()[0]
        else:
            match = re.search(r"(#C\d{3,})", cast(str, source_url))
            source_ident = match.groups()[0] if match else source_ident
    if not source_url:
        source_url = cast(HttpUrl, wikicommons_url)

    author = AuthorSchema(name=author_name, url=author_url) if author_name else None
    source = SourceSchema(url=source_url, name=source_name, ident=source_ident)

    # Return structured data using Pydantic
    return PhotoSchema(
        licenses=licenses,
        caption=captions,
        author=author,
        source=source,
        raw_url=image_url,
        width=width,
        height=height,
        url=wikicommons_url,
        capture_date=img_date,
        comment="",
    )


class WikicommonsService:
    """Service to get photo from
    [Wikimedia Commons](https://commons.wikimedia.org).

    Note:
        This is only used to get photo information, not to get huts!
    """

    def __init__(
        self,
        request_url: str = "https://magnus-toolserver.toolforge.org/commonsapi.php",
        max_dimension: int = 3600,
    ):
        super().__init__()
        self.request_url = request_url
        self._max_dimension = max_dimension

    def get_photo(self, filename: str) -> PhotoSchema:
        return get_wikicommon_photo_info(filename=filename, api_url=self.request_url, max_dimension=self._max_dimension)

    def get_huts_from_source(self, bbox: BBox | None = None, limit: int = 1, offset: int = 0, **kwargs: dict) -> list:
        raise NotImplementedError("Get huts from source not implemented for WikiCommons.")

    def convert(self, src: t.Mapping | t.Any) -> HutSchema:
        raise NotImplementedError("Get huts from source not implemented for WikiCommons.")


wikicommons_service = WikicommonsService()

if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)

    # File names to query
    file_names = ["Wildhornhuette.jpg", "Lohner hut SAC.jpg", "RifugioVallanta.jpg", "Refuge d'Ambin.jpeg"]

    for file_name in file_names:
        try:
            image_info = wikicommons_service.get_photo(file_name)
            print(image_info)
        except ValidationError as e:
            print("Validation error:", e)
        # except Exception as ex:
        #    print("Error:", ex)
