import logging
from datetime import datetime
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageFile
from pydantic_string_url import HttpUrl

# from numpy import imag
from hut_services.core.cache import file_cache
from hut_services.core.schema._license import AuthorSchema, LicenseSchema, SourceSchema
from hut_services.core.schema._photo import PhotoSchema
from hut_services.core.schema.locale import TranslationSchema

logger = logging.getLogger(__name__)

refuges_lic = LicenseSchema(
    slug="cc-by-sa-2.0", name="CC-BY-SA 2.0", url="https://creativecommons.org/licenses/by-sa/2.0/"
)


@file_cache()
def _get_image_size(url: HttpUrl) -> tuple[int, int]:
    response = requests.get(url, stream=True, timeout=10)
    image_data = BytesIO()
    image_file = ImageFile.Parser()
    counter = 0
    for chunk in response.iter_content(4096):
        image_data.write(chunk)
        image_file.feed(chunk)
        counter += 1
        if image_file.image:
            print(f"Image size determined after {counter} iterations")
            return image_file.image.size
    return 0, 0


@file_cache()
def _get_original_images_request(hut_id: str) -> bytes:
    url = f"https://www.refuges.info/point/{hut_id}"
    response = requests.get(url, timeout=10)
    return response.content


def get_original_images(hut_id: str) -> list[PhotoSchema]:
    soup = BeautifulSoup(_get_original_images_request(hut_id), "html.parser")
    comments = soup.find_all("li")
    original_images = []
    for comment in comments:
        image_tag = comment.find("img")
        if image_tag:
            image_url = f"https://www.refuges.info{image_tag.parent['href']}".split("?")[0]
            image_url = image_url.replace("-reduite", "-originale")
            capture_date_str = comment.find("div", class_="texte_sur_image").text
            capture_date = datetime.strptime(capture_date_str, "%d/%m/%Y")
            caption = TranslationSchema(
                fr=comment.find("blockquote").text.strip(),
            )
            author_name = comment.find("p", class_="fauxfieldset-legend").text.split("par")[1].strip()
            author = AuthorSchema(name=author_name)
            src_ident = comment.find("a")["id"]
            src_url = f"https://www.refuges.info/point/{hut_id}#{src_ident}"
            source = SourceSchema(name="refuges.info", url=src_url, ident=src_ident)
            width, height = _get_image_size(image_url)
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
    from rich import print as rprint

    photos = get_original_images("9819")
    rprint(photos)
