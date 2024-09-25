import re
from datetime import datetime
from typing import Any, Optional, cast
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl, ValidationError
from rich import print

from hut_services import TranslationSchema, file_cache


# TODO: use schemas from core/schema/_photo.py
class LicenseInfo(BaseModel):
    slug: str
    url: HttpUrl | None = None
    name: str | None = None


class AuthorInfo(BaseModel):
    name: str
    url: Optional[HttpUrl] = None


class SourceInfo(BaseModel):
    url: Optional[HttpUrl] = None
    name: Optional[str] = None
    ident: Optional[str] = None


class WikimediaImageInfo(BaseModel):
    licenses: list[LicenseInfo]
    caption: TranslationSchema
    author: Optional[AuthorInfo] = None
    source: Optional[SourceInfo] = None
    image_url: Optional[HttpUrl] = None
    width: Optional[int] = None
    height: Optional[int] = None
    url: HttpUrl
    date: datetime | None


def parse_href_html_field(html: Optional[str]) -> tuple[str, HttpUrl | None]:
    """Parse an HTML field to extract plain text and URL (if present)."""
    if not html:
        return "", None
    soup = BeautifulSoup(html, "html.parser")
    if soup.a:
        name = soup.a.text or ""
        url = soup.a.get("href")
        if isinstance(url, list):
            url = url[0]
        url_cast = cast(HttpUrl, url) if url is not None else None
        return name, url_cast
    else:
        return html.strip(), None


def parse_time_html_field(html: str | None) -> datetime | None:
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    time_tag = soup.find("time", class_="dtstart")
    if time_tag:
        datetime_str = time_tag.get("datetime")
        try:
            return datetime.strptime(datetime_str, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Handle other possible date formats or raise an error
                return None
    return None


def extract_hostname(url: str) -> str:
    """Extract the hostname from a full URL."""
    parsed_url = urlparse(url)
    return parsed_url.hostname if parsed_url.hostname else url


def resize_image_url(url: str, max_dimension: int) -> str:
    """Resize the image URL if width or height exceeds max_dimension."""
    filename = url.split("/")[-1]
    return (url + f"/{max_dimension}px-{filename}").replace("commons/", "commons/thumb/")


@file_cache()
def get_wikimedia_image_info(file_name: str, max_dimension: int = 3000) -> WikimediaImageInfo:
    """Fetch image information from Magnus Toolserver API and return structured data using Pydantic."""
    api_url = f"https://magnus-toolserver.toolforge.org/commonsapi.php?image={file_name}"
    response = requests.get(api_url, timeout=20)

    if response.status_code != 200:
        err_msg = f"Error fetching data from Magnus Toolserver: {response.status_code}"
        raise Exception(err_msg)  # noqa: TRY002

    # Parse XML response
    root = ET.fromstring(response.content)  # noqa: S314

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
    img_date = parse_time_html_field(cast(str, file_info_find("date")))

    wikicommons_url = f"https://commons.wikimedia.org/wiki/{quote(title)}"
    # Resize the image URL if width or height is greater than max_dimension
    if image_url and width and height and (width > max_dimension or height > max_dimension):
        image_url = resize_image_url(image_url, max_dimension)
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
        licenses.append(LicenseInfo(slug=license_slug, url=license_info_url, name=license_name))

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
    author_name, author_url = parse_href_html_field(author_raw)
    source_name, source_url = parse_href_html_field(source_raw)

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
        source_url = match.group() if match else source_url
    if "refuges.info" in source_name.lower():
        source_name = "refuges"
        match = re.search(r"(\d{3,})-originale", cast(str, source_url))
        if match:
            source_ident = match.groups()[0]
        else:
            match = re.search(r"(#C\d{3,})", cast(str, source_url))
            source_ident = match.groups()[0] if match else source_ident
    if not source_url:
        source_url = cast(HttpUrl, wikicommons_url)

    source = SourceInfo(url=source_url, name=source_name, ident=source_ident)
    author = AuthorInfo(name=author_name, url=author_url) if author_name else None

    # Return structured data using Pydantic
    return WikimediaImageInfo(
        licenses=licenses,
        caption=captions,
        author=author,
        source=source,
        image_url=cast(HttpUrl, image_url),
        width=width,
        height=height,
        url=cast(HttpUrl, wikicommons_url),
        date=img_date,
    )


if __name__ == "__main__":
    # File names to query
    file_names = ["Wildhornhuette.jpg", "Lohner hut SAC.jpg", "RifugioVallanta.jpg", "Refuge d'Ambin.jpeg"]

    for file_name in file_names:
        try:
            image_info = get_wikimedia_image_info(file_name, max_dimension=500)
            print(image_info)
        except ValidationError as e:
            print("Validation error:", e)
        # except Exception as ex:
        #    print("Error:", ex)
