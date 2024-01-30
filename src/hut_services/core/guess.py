import re
from typing import Literal

from slugify import slugify

__all__ = ["guess_slug_name", "guess_hut_type"]

from hut_services.core.schema._hut_fields import (
    AnswerEnum,
    CapacitySchema,
    HutTypeEnum,
    HutTypeSchema,
    OpenMonthlySchema,
)

HUT_NAMES = [r"huette", r"r[ie]fug[ei]", r"h[iü]tt[ae]", r"camona", r"capanna", r"cabane", r"huisli"]
BIVI_NAMES = [r"biwak", r"bivouac", r"bivacco"]
BASIC_HOTEL_NAMES = [r"berghotel", r"berggasthaus", r"auberge", r"gasthaus", r"berghaus"]
CAMPING_NAMES = [r"camping", r"zelt"]
HOTEL_NAMES = [r"h[oô]tel"]
HOSTEL_NAMES = [r"hostel", r"jugendherberg"]
RESTAURANT_NAMES = [r"restaurant", r"ristorante", r"beizli"]
_ALP_NAMES = ["alp", "alm", "hof"]


def _in(patterns: list, target: str) -> bool:
    return any(re.search(pat.lower(), target.lower()) for pat in patterns)


def guess_hut_type(
    name: str = "",
    default: HutTypeEnum = HutTypeEnum.unknown,
    capacity: CapacitySchema | None = None,
    elevation: float | None = 1500,
    operator: Literal["sac", "dav"] | None = None,
    osm_tag: str | None = "",
    missing_walls: int | None | str = 0,
    open_monthly: OpenMonthlySchema | None = None,
    # ) -> HutType:
) -> HutTypeSchema:
    """Guess hut type based on some input parameters.

    Args:
        name: hut name
        default: default type if nothing else fits
        capacity: capacity for a open and closed hut
        operator: who is operating the hut
        osm_tag: osm toursm tag
        missing_walls: missing_walls value from refuges.info
        open_monthly: list which month it is open"""
    # check if every month is closed
    is_closed = False if open_monthly is None else all(o == AnswerEnum.no for o in open_monthly)
    # if capacity is not None and capacity.if_open == 0 and capacity.if_closed in (0, None):
    #    is_closed = True

    name = name or ""
    capacity_open = capacity.if_open or 0 if capacity is not None else 0
    capacity_closed = capacity.if_closed or 0 if capacity is not None else 0
    elevation = elevation or 1500
    osm_tag = osm_tag or ""
    missing_walls = missing_walls or 0
    if isinstance(missing_walls, str):
        try:
            missing_walls = int(missing_walls)
        except ValueError:
            missing_walls = 0

    name = name.lower()
    _possible_hut = _in(HUT_NAMES, name)
    slug_open = default
    if is_closed:
        slug_open = HutTypeEnum.closed
    elif _in(BASIC_HOTEL_NAMES, name):
        slug_open = HutTypeEnum.bhotel
    elif _in(HOTEL_NAMES, name):
        slug_open = HutTypeEnum.hotel
    elif _in(HOSTEL_NAMES, name):
        slug_open = HutTypeEnum.hostel
    elif _in(RESTAURANT_NAMES, name):
        slug_open = HutTypeEnum.resta
    elif _in(CAMPING_NAMES, name):
        slug_open = HutTypeEnum.camping
    elif osm_tag == "wilderness_hut" or missing_walls > 0:
        slug_open = HutTypeEnum.bivouac if elevation > 2500 and not _possible_hut else HutTypeEnum.shelter
    elif (capacity_open == capacity_closed or capacity_open < 22) and capacity_open > 0:
        slug_open = HutTypeEnum.bivouac if elevation > 2500 and not _possible_hut else HutTypeEnum.selfhut
    elif _possible_hut:
        slug_open = HutTypeEnum.hut
    elif _in(BIVI_NAMES, name):
        slug_open = HutTypeEnum.selfhut if elevation < 2200 else HutTypeEnum.bivouac
    elif _in(_ALP_NAMES, name) and elevation < 2000:
        slug_open = HutTypeEnum.alp
    elif operator in ["sac", "dav"] or osm_tag == "alpine_hut":
        slug_open = HutTypeEnum.hut
    slug_closed = None
    if slug_open == HutTypeEnum.hut and capacity_open > 0 and capacity_open != capacity_closed:
        if (capacity is not None and capacity.if_closed is not None) and capacity.if_closed == 0:
            slug_closed = HutTypeEnum.closed
        elif (capacity is not None and capacity.if_closed is not None) and capacity.if_closed > 0:
            slug_closed = HutTypeEnum.selfhut if elevation < 3000 else HutTypeEnum.bivouac
    return HutTypeSchema(open=slug_open, closed=slug_closed)


def guess_slug_name(hut_name: str, max_length: int = 25, min_length: int = 4) -> str:
    REPLACE_IN_SLUG = [
        "alpage",
        "alpina",
        "huette",
        "cabanne",
        "cabane",
        "capanna",
        "chamana",
        "chamanna",
        "chamonna",
        "chalet",
        "capanna",
        "biwak",
        "bivouac",
        "bivacco",
        "berghotel",
        "chalets",
        "camona",
        "hotel",
        "huette",
        "naturfreundehaus",
        "naturfreunde",
        "berghuette",
        "berggasthaus",
        "waldhuette",
        "berghaus",
        "cascina",
        "rifugio",
        "refuge",
        "citta",
        "guide",
    ]
    NOT_IN_SLUG = [
        *REPLACE_IN_SLUG,
        "alp",
        "alpe",
        "gite",
        "casa",
        "sac",
        "cas",
        "caf",
        "cai",
        "del",
        "des",
        "rif",
        "abri",
        "sur",
        "ski",
        "aacz",
        "aacb",
    ]

    for r in ("ä", "ae"), ("ü", "ue"), ("ö", "oe"):
        hut_name = hut_name.lower().replace(r[0], r[1])
    slug = slugify(hut_name)
    slug = re.sub(r"[0-9]", "", slug)  # remove numbers
    slug = slug.strip(" -")
    slugs = slug.split("-")
    slugl = [s for s in slugs if (s not in NOT_IN_SLUG and len(s) >= 3)]
    for _replace in REPLACE_IN_SLUG:
        slugl = [
            v.replace(_replace, "") if len(v.replace(_replace, "")) > 4 else v for v in slugl if v.replace(_replace, "")
        ]
    if not slugl or len("-".join(slugl)) < min_length:
        slugl = slugify(hut_name).split("-")
    return slugify(" ".join(slugl), max_length=max_length, word_boundary=True)
