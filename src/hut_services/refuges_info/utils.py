import logging
import time
from io import BytesIO

import dateparser
import requests
from bs4 import BeautifulSoup
from PIL import ImageFile
from pydantic_string_url import HttpUrl

# if __name__ == "__main__":
from rich import print as rprint

# from numpy import imag
from hut_services.core.cache import file_cache
from hut_services.core.schema._license import LicenseSchema, SourceSchema
from hut_services.core.schema._photo import PhotoSchema
from hut_services.core.schema.locale import TranslationSchema

logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("chardet").setLevel(logging.WARNING)
logging.getLogger("tzlocal").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

refuges_lic = LicenseSchema(
    slug="cc-by-sa-2.0", name="CC-BY-SA 2.0", url="https://creativecommons.org/licenses/by-sa/2.0/"
)


@file_cache(forever=True)
def _get_image_size(url: HttpUrl, _delay: float = 0.2) -> tuple[int, int]:
    response = requests.get(url, stream=True, timeout=15)
    image_data = BytesIO()
    image_file = ImageFile.Parser()
    time.sleep(_delay)
    for counter, chunk in enumerate(response.iter_content(4096)):
        image_data.write(chunk)
        image_file.feed(chunk)
        if image_file.image:
            logger.debug(f"Image size determined after {counter+1} iterations ({url})")
            return image_file.image.size
    return 0, 0


@file_cache(forever=True)
def _get_original_images_request(hut_id: str, _delay: float = 1.5) -> bytes:
    url = f"https://www.refuges.info/point/{hut_id}"
    response = requests.get(url, timeout=15)
    time.sleep(_delay)
    return response.content


@file_cache()
def get_original_images(hut_id: str) -> list[PhotoSchema]:
    soup = BeautifulSoup(_get_original_images_request(hut_id), "html.parser")
    comments = soup.find_all("li")
    original_images = []
    for comment in comments:
        photos_div = comment.find("div", class_="photos")
        if not photos_div:
            continue
        image_link = photos_div.find("a")
        if not image_link:
            continue
        image_url = f"https://www.refuges.info{image_link['href']}".split("?")[0]
        # Get date from texte_sur_image div
        date_div = photos_div.find("div", class_="texte_sur_image")
        if not date_div:
            continue
        capture_date_str_fr = date_div.text.strip()
        try:
            capture_date = dateparser.parse(capture_date_str_fr, languages=["fr"]) if capture_date_str_fr else None
        except ValueError:
            logger.warning(f"Could not parse date: {capture_date_str_fr} for hut {hut_id}")
            capture_date = None
        # Get caption from blockquote if it exists
        blockquote = comment.find("blockquote")
        caption = TranslationSchema(fr=blockquote.text.strip()) if blockquote else TranslationSchema()
        # Get author - currently not available in new structure
        author = None
        # Get source info
        src_ident = f"C{image_url.split('/')[-1].split('-')[0]}"  # Extract ID from image URL
        src_url = f"https://www.refuges.info/point/{hut_id}#{src_ident}"
        source = SourceSchema(name="refuges.info", url=src_url, ident=src_ident)
        width, height = 0, 0  # _get_image_size(image_url)
        photo_schema = PhotoSchema(
            raw_url=image_url,
            url=src_url,
            capture_date=capture_date,
            caption=caption,
            comment="",
            author=author,
            source=source,
            width=width,
            height=height,
            licenses=[refuges_lic],
        )
        original_images.append(photo_schema)
    return original_images


if __name__ == "__main__":
    photos = get_original_images("9819")
    rprint(photos)
