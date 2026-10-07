"""Fetch and parse hut page images from www.doc.govt.nz.

One cached page request per hut provides everything: the real page URL
(``/link/<uuid>.aspx`` 301-redirects to it), the hero image (with its
info-button credit: caption, author, license) and the gallery images
(``doc-fancy-image`` entries with ``Image: author | license`` credits).

License rules (see https://www.doc.govt.nz/footer-links/copyright/):
site default is Crown Copyright under CC BY 4.0 ("DOC"); images credited
with a Creative Commons link keep that exact license; images marked with
a plain ``(c)`` (third party copyright) are NOT included.
"""

import logging
import re
import typing as t

import httpx
from PIL import ImageFile

from hut_services import AuthorSchema, LicenseSchema, PhotoSchema, SourceSchema, TranslationSchema, file_cache

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"}

DOC_SITE = "https://www.doc.govt.nz"
COPYRIGHT_URL = f"{DOC_SITE}/footer-links/copyright/"
DOC_CROWN_LICENSE = LicenseSchema(
    slug="CC-BY-4.0",
    url="https://creativecommons.org/licenses/by/4.0/",
    name="Crown Copyright (Department of Conservation), CC BY 4.0",
)
CC_NAMES: dict[str, str] = {
    "by": "Attribution",
    "by-sa": "Attribution-ShareAlike",
    "by-nc": "Attribution-NonCommercial",
    "by-nc-sa": "Attribution-NonCommercial-ShareAlike",
    "by-nd": "Attribution-NoDerivatives",
    "by-nc-nd": "Attribution-NonCommercial-NoDerivatives",
    "cc0": "Zero",
}

_HERO_BLOCK = re.compile(r'<section class="doc-main-layout__hero">.*?</section>', re.S)
_HERO_CAPTION = re.compile(r'<doc-image-caption caption="([^"]*)">\s*<div class="hide-content">(.*?)</div>', re.S)
_HERO_IMAGES = re.compile(r'(?:srcset="|src=")(/thumbs/hero/[^"\s]+?\.(?:jpg|jpeg|png|webp))')
_FANCY = re.compile(r'<doc-fancy-image\s+src="([^"]+)"\s+caption="([^"]*)"', re.S)
_FANCY_THUMB = re.compile(r'<doc-image[^>]*src="(/thumbs/gallery/[^"]+)"')
_CC_URL = re.compile(r"https?://creativecommons\.org/licenses/(?P<code>[a-z0-9-]+)/(?P<ver>\d+\.\d+)/")


def _unescape(text: str) -> str:
    """DOC escapes captions twice (HTML inside an attribute)."""
    import html

    return html.unescape(html.unescape(text))


def _strip_tags(text: str) -> str:
    import html

    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


@file_cache(forever=True)
def resolve_page_url(static_link: str) -> str:
    """Resolve a `/link/<uuid>.aspx` source link to the real page URL (redirect)."""
    r = httpx.head(static_link, follow_redirects=True, timeout=15, headers=_HEADERS)
    r.raise_for_status()
    return str(r.url)


@file_cache()
def _fetch_page(static_link: str) -> tuple[str, str]:
    """Fetch a hut page: returns `(real_url, html)` (file-cached)."""
    r = httpx.get(static_link, follow_redirects=True, timeout=20, headers=_HEADERS)
    r.raise_for_status()
    return str(r.url), r.text


@file_cache(forever=True)
def _image_size(url: str) -> tuple[int, int]:
    """Image size via partial download (first parser hit wins)."""
    parser = ImageFile.Parser()
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=15, headers=_HEADERS) as r:
            for chunk in r.iter_bytes(2048):
                parser.feed(chunk)
                if parser.image:
                    return t.cast("tuple[int, int]", parser.image.size)
    except OSError as e:
        logger.warning(f"cannot determine image size for {url}: {e!r}")
    return 0, 0


def _parse_credit(credit_html: str) -> tuple[str | None, str | None, LicenseSchema | None, bool]:
    """Parse an ``Image: author | license`` credit.

    Returns ``(author_name, author_url, license, skip)`` — ``skip`` is True
    for third party copyright (plain ``(c)``, no reusable license).
    """
    cc = _CC_URL.search(credit_html)
    author = _parse_author(credit_html)
    if cc:
        code, ver = cc.group("code"), cc.group("ver")
        name = CC_NAMES.get(code, code)
        return (
            author,
            None,
            LicenseSchema(slug=f"CC-{code.upper()}-{ver}", url=cc.group(0), name=f"Creative Commons {name} {ver}"),
            False,
        )
    if "copyright" in credit_html or ">DOC<" in _unescape(credit_html) or _strip_tags(credit_html).endswith("DOC"):
        return author, None, DOC_CROWN_LICENSE, False
    if "©" in _unescape(credit_html) or "&copy;" in credit_html:
        return author, None, None, True  # third party (c): not interested
    if author:
        return author, None, None, True  # named author without a license marker: rights unclear -> skip
    return author, None, DOC_CROWN_LICENSE, False  # no credit at all: site default (Crown CC BY 4.0)


def _parse_author(credit_html: str) -> str | None:
    """Author name (link text if the author is a link, else the plain text)."""
    m = re.search(r"<a[^>]*>([^<]+)</a>\s*\|", credit_html) or re.search(
        r"</span>\s*([^<>]+?)\s*<span>\s*\|", credit_html
    )
    if m and m.group(1).strip():
        return m.group(1).strip()
    text = _strip_tags(re.sub(r"\|.*", "", credit_html)).replace("Image:", "").strip()
    return text or None


def _photo(
    src: str, caption: str, credit: str, real_url: str, static_link: str, source_ident: str
) -> PhotoSchema | None:
    """Build one PhotoSchema (None when the license is third party (c))."""
    author_name, author_url, license_, skip = _parse_credit(credit)
    if skip or license_ is None:
        return None
    raw_url = src if src.startswith("http") else DOC_SITE + src
    width, height = _image_size(raw_url)
    return PhotoSchema(
        raw_url=raw_url,
        url=real_url,  # the hut's own page
        source=SourceSchema(name="doc_nz", ident=source_ident, url=static_link),
        author=AuthorSchema(name=author_name or "Department of Conservation Te Papa Atawhai", url=author_url)
        if author_name or license_ is DOC_CROWN_LICENSE
        else None,
        licenses=[license_],
        caption=TranslationSchema(en=caption) if caption else TranslationSchema(),
        width=width,
        height=height,
        capture_date=None,
    )


def _hero_uuid(html: str) -> str | None:
    m = re.search(r"/thumbs/hero/contentassets/([0-9a-f]{32})/", html)
    return m.group(1) if m else None


def parse_page_images(html: str, real_url: str, static_link: str) -> list[PhotoSchema]:
    """Parse hero + gallery images from a hut page (license-filtered)."""
    photos: list[PhotoSchema] = []
    hero_uuid = _hero_uuid(html)
    hero = _HERO_BLOCK.search(html)
    if hero:
        block = hero.group(0)
        cap_match = _HERO_CAPTION.search(block)
        caption = _unescape(cap_match.group(1)) if cap_match else ""
        credit = cap_match.group(2) if cap_match else ""
        sources = _HERO_IMAGES.findall(block)
        if sources:

            def _width(s: str) -> int:
                wm = re.search(r"-(\d+)\.", s)
                return int(wm.group(1)) if wm else 0

            best = max(sources, key=_width)
            src = best if best.startswith("http") else DOC_SITE + best
            ident = hero_uuid or best.rsplit("/", 1)[-1]
            photo = _photo(src, caption, credit, real_url, static_link, ident)
            if photo:
                photos.append(photo)
    # gallery: dedupe the hero (its gallery thumb repeats the hero contentasset)
    for m in _FANCY.finditer(html):
        src, caption_attr = m.group(1), m.group(2)
        caption_full = _unescape(caption_attr)
        caption, _, credit = caption_full.partition(" Image:")
        if not credit:
            credit = caption_full  # no credit part at all -> site default handling in _parse_credit
            caption = caption_full
        thumb = _FANCY_THUMB.search(html[m.end() : m.end() + 400])
        thumb_src = thumb.group(1) if thumb else ""
        if hero_uuid and f"contentassets/{hero_uuid}" in thumb_src:
            continue  # hero repeated in the gallery
        uuid_m = re.search(r"link/([0-9a-f]{32})", thumb_src)
        ident = uuid_m.group(1) if uuid_m else (src.rsplit("/", 1)[-1] or src)
        photo = _photo(src, caption.strip(), credit, real_url, static_link, ident)
        if photo:
            photos.append(photo)
    return photos


@file_cache()
def get_hut_images(static_link: str) -> list[PhotoSchema]:
    """Photos for one hut: page request (cached) + one partial download per photo.

    Raises on fetch errors (so nothing broken gets cached); the converter
    catches and degrades to no photos.
    """
    real_url, html = _fetch_page(static_link)
    if "<html" not in html[:2000].lower():
        # some /link/ uuids point at assets (e.g. the introduction thumbnail image)
        logger.warning(f"hut page link {static_link} did not return HTML but {real_url}")
        return []
    return parse_page_images(html, real_url, static_link)
