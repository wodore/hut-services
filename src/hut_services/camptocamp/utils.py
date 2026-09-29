"""Utilities to get image data from camptocamp.org."""

import logging
import time
import typing as t
from datetime import datetime

import httpx

from hut_services.core.cache import file_cache
from hut_services.core.schema._license import AuthorSchema, LicenseSchema, SourceSchema
from hut_services.core.schema._photo import PhotoSchema
from hut_services.core.schema.locale import TranslationSchema

logger = logging.getLogger(__name__)

MEDIA_URL = "https://media.camptocamp.org/c2corg-active"
"""Base URL to the raw image files."""

IMAGE_URL = "https://api.camptocamp.org/images"
"""Base URL to the image API endpoint."""

# Languages supported by `TranslationSchema`.
_SUPPORTED_LANGS = ("de", "en", "fr", "it")

# Camptocamp distinguishes 'collaborative' and 'personal' images, they come with different licenses.
collaborative_lic = LicenseSchema(
    slug="cc-by-sa-3.0", name="CC BY-SA 3.0", url="https://creativecommons.org/licenses/by-sa/3.0/"
)
personal_lic = LicenseSchema(
    slug="cc-by-nc-nd-3.0", name="CC BY-NC-ND 3.0", url="https://creativecommons.org/licenses/by-nc-nd/3.0/"
)


@file_cache(forever=True)
def _get_image_request(image_id: int, _delay: float = 0.2) -> dict[str, t.Any] | None:
    """Request image details from the camptocamp API."""
    try:
        r = httpx.get(f"{IMAGE_URL}/{image_id}", timeout=30)
        r.raise_for_status()
        time.sleep(_delay)  # be nice to the API
        return t.cast(dict[str, t.Any], r.json())
    except httpx.HTTPError:
        logger.exception(f"HTTP error occurred fetching image {image_id}")
        return None
    except Exception:
        logger.exception(f"Error fetching image data for {image_id}")
        return None


def _get_caption(locales: list[t.Any]) -> TranslationSchema:
    """Build the caption from the image locales."""
    caption = TranslationSchema()
    for locale in locales:
        lang = locale.get("lang")
        title = locale.get("title")
        if lang in _SUPPORTED_LANGS and title:
            setattr(caption, lang, title)
    return caption


def _parse_image(image_id: int, data: dict[str, t.Any]) -> PhotoSchema | None:
    """Parse image details into a `PhotoSchema`."""
    filename = data.get("filename")
    width = data.get("width")
    height = data.get("height")
    if not filename or not width or not height:
        logger.debug(f"Skip image {image_id}: no filename or no dimensions")
        return None

    license_ = personal_lic if data.get("image_type") == "personal" else collaborative_lic
    author_name = data.get("author")
    creator = data.get("creator")
    if not author_name and isinstance(creator, dict):
        author_name = creator.get("name")
    author = AuthorSchema(name=author_name) if author_name else None

    image_page_url = f"https://www.camptocamp.org/images/{image_id}"
    capture_date = None
    date_time = data.get("date_time")
    if date_time and not date_time.startswith("1970-01-01"):
        try:
            capture_date = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        except ValueError:
            logger.debug(f"Could not parse capture date of image {image_id}: {date_time}")
    categories = data.get("categories")

    return PhotoSchema(
        licenses=[license_],
        caption=_get_caption(data.get("locales", [])),
        source=SourceSchema(name="camptocamp", ident=str(image_id), url=image_page_url),
        author=author,
        comment="",
        raw_url=f"{MEDIA_URL}/{filename}",
        width=width,
        height=height,
        url=image_page_url,
        capture_date=capture_date,
        tags=set(categories) if categories else None,
    )


def get_images(image_ids: tuple[int, ...]) -> list[PhotoSchema]:
    """Get photos for the given camptocamp image document ids."""
    photos = []
    for image_id in image_ids:
        data = _get_image_request(image_id)
        if data is None:
            continue
        photo = _parse_image(image_id, data)
        if photo is not None:
            photos.append(photo)
    return photos


if __name__ == "__main__":
    from rich import print as rprint

    rprint(get_images((167028,)))
