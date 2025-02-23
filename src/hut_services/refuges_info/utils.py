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
from hut_services.core.schema._license import AuthorSchema, LicenseSchema, SourceSchema
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
        image_tag = comment.find("img")
        if image_tag:
            image_url = f"https://www.refuges.info{image_tag.parent['href']}".split("?")[0]
            image_url = image_url.replace("-reduite", "-originale")
            try:
                fauxfieldset_legend_split = comment.find("p", class_="fauxfieldset-legend").text.split("par")
            except AttributeError:
                continue
            capture_date_str_fr = fauxfieldset_legend_split[0].strip()
            _capture_date_str_image = comment.find("div", class_="texte_sur_image").text  # date in the image - not used

            try:
                capture_date = dateparser.parse(capture_date_str_fr, languages=["fr"])
            except ValueError:
                rprint(comment)
                rprint(capture_date_str_fr)
                rprint(_capture_date_str_image)
                rprint(f"https://www.refuges.info/point/{hut_id}")
                raise
            try:
                caption = TranslationSchema(
                    fr=comment.find("blockquote").text.strip(),
                )
            except AttributeError:
                # no comment to the image
                caption = TranslationSchema()
            author_name = fauxfieldset_legend_split[1].strip() if len(fauxfieldset_legend_split) > 1 else ""
            author = AuthorSchema(name=author_name) if author_name else None
            src_ident = comment.find("a")["id"]
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
