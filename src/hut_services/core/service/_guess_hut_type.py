import re

from hut_services import HutTypeEnum, HutTypeSchema


def guess_hut_type(
    name: str = "",
    capacity_open: int | None = 0,
    capacity_closed: int | None = 0,
    elevation: float | None = 1500,
    operator: str | None = "",
    osm_tag: str | None = "",
    missing_walls: int | None | str = 0,
    # ) -> HutType:
) -> HutTypeSchema:
    if name is None:
        name = ""
    if capacity_open is None:
        capacity_open = 0
    orig_capacity_shelter = capacity_closed
    if capacity_closed is None:
        capacity_closed = 0
    if elevation is None:
        elevation = 1500
    if operator is None:
        operator = ""
    if osm_tag is None:
        osm_tag = ""
    if missing_walls is None:
        missing_walls = 0
    if isinstance(missing_walls, str):
        try:
            missing_walls = int(missing_walls)
        except ValueError:
            missing_walls = 0

    def _in(patterns: list, target: str) -> bool:
        return any(re.search(pat.lower(), target.lower()) for pat in patterns)

    name = name.lower()
    _hut_names = [r"huette", r"h[iü]tt[ae]", r"camona", r"capanna", r"cabane", r"huisli"]
    _bivi_names = [r"r[ie]fug[ei]", r"biwak", r"bivouac", r"bivacco"]
    _basic_hotel_names = [r"berghotel", r"berggasthaus", r"auberge", r"gasthaus", r"berghaus"]
    _camping_names = [r"camping", r"zelt"]
    _hotel_names = [r"h[oô]tel"]
    _hostel_names = [r"hostel", r"jugendherberg"]
    _restaurant_names = [r"restaurant", r"ristorante", r"beizli"]
    _alp_names = ["alp", "alm", "hof"]
    _possible_hut = _in(_hut_names, name)
    slug_open = HutTypeEnum.unknown
    if _in(_basic_hotel_names, name):
        slug_open = HutTypeEnum.basic_hotel
    elif _in(_hotel_names, name):
        slug_open = HutTypeEnum.hotel
    elif _in(_hostel_names, name):
        slug_open = HutTypeEnum.hostel
    elif _in(_restaurant_names, name):
        slug_open = HutTypeEnum.restaurant
    elif _in(_camping_names, name):
        slug_open = HutTypeEnum.camping
    elif osm_tag == "wilderness_hut" or missing_walls > 0:
        slug_open = HutTypeEnum.bivouac if elevation > 2500 and not _possible_hut else HutTypeEnum.basic_shelter
    elif (capacity_open == capacity_closed or capacity_open < 22) and capacity_open > 0:
        slug_open = HutTypeEnum.bivouac if elevation > 2500 and not _possible_hut else HutTypeEnum.unattended_hut
    elif _possible_hut:
        slug_open = HutTypeEnum.hut
    elif _in(_bivi_names, name):
        slug_open = HutTypeEnum.bivouac
    elif _in(_alp_names, name) and elevation < 2000:
        slug_open = HutTypeEnum.alp
    elif operator in ["sac", "dav"] or osm_tag == "alpine_hut":
        slug_open = HutTypeEnum.hut
    slug_closed = None
    if slug_open == HutTypeEnum.hut and capacity_open > 0 and capacity_open != capacity_closed:
        if orig_capacity_shelter is not None and orig_capacity_shelter == 0:
            slug_closed = HutTypeEnum.closed
        else:
            slug_closed = HutTypeEnum.unattended_hut if elevation < 2500 else HutTypeEnum.bivouac
    return HutTypeSchema(open=slug_open, closed=slug_closed)
