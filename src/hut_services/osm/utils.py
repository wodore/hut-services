import re

from hut_services import HutTypeEnum


def guess_hut_type(
    name: str = "",
    capacity: int | None = 0,
    capacity_shelter: int | None = 0,
    elevation: float | None = 1500,
    organization: str | None = "",
    osm_tag: str | None = "",
    # ) -> HutType:
) -> HutTypeEnum:
    if name is None:
        name = ""
    if capacity is None:
        capacity = 0
    if capacity_shelter is None:
        capacity_shelter = 0
    if elevation is None:
        elevation = 1500
    if organization is None:
        organization = ""
    if osm_tag is None:
        osm_tag = ""

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
    _possible_hut = _in(_hut_names, name)
    _slug = HutTypeEnum.unknown
    if _in(_basic_hotel_names, name):
        _slug = HutTypeEnum.basic_hotel
    elif _in(_hotel_names, name):
        _slug = HutTypeEnum.hotel
    elif _in(_hostel_names, name):
        _slug = HutTypeEnum.hostel
    elif _in(_restaurant_names, name):
        _slug = HutTypeEnum.restaurant
    elif _in(_camping_names, name):
        _slug = HutTypeEnum.camping
    elif osm_tag == "wilderness_hut":
        _slug = HutTypeEnum.bivouac if elevation > 2500 and not _possible_hut else HutTypeEnum.basic_shelter
    elif (capacity == capacity_shelter or capacity < 22) and capacity > 0:
        _slug = HutTypeEnum.bivouac if elevation > 2500 and not _possible_hut else HutTypeEnum.unattended_hut
    elif _possible_hut:
        _slug = HutTypeEnum.hut
    elif _in(_bivi_names, name):
        _slug = HutTypeEnum.bivouac
    elif _in(["alp", "alm", "hof"], name) and elevation < 2000:
        _slug = HutTypeEnum.alp
    elif organization in ["sac", "dav"] or osm_tag == "alpine_hut":
        _slug = HutTypeEnum.hut
    return _slug
