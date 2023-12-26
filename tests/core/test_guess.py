from typing import Any

import pytest
from hut_services import CapacitySchema, HutTypeEnum, HutTypeSchema
from hut_services.core.guess import guess_hut_type, guess_slug_name


@pytest.mark.parametrize(
    "params,expected",
    [
        (
            {"name": "Waldhuette", "capacity": CapacitySchema(open=40, closed=12), "elevation": 2400.0},
            HutTypeSchema(open=HutTypeEnum.hut, closed=HutTypeEnum.selfhut),
        ),
        (
            {"name": "Berghuette", "capacity": CapacitySchema(open=40, closed=12), "elevation": 3400.0},
            HutTypeSchema(open=HutTypeEnum.hut, closed=HutTypeEnum.bivouac),
        ),
        (
            {
                "name": "Irgend ein Name",
                "capacity": CapacitySchema(open=40, closed=None),
                "elevation": 2000.0,
                "operator": "sac",
            },
            HutTypeSchema(open=HutTypeEnum.hut, closed=None),
        ),
        (
            {"name": "Ohne Beartung", "capacity": CapacitySchema(open=15, closed=None), "operator": "sac"},
            HutTypeSchema(open=HutTypeEnum.selfhut, closed=None),
        ),
        (
            {"name": "Musterbiwak", "capacity": CapacitySchema(open=20, closed=None), "elevation": 2800.0},
            HutTypeSchema(open=HutTypeEnum.bivouac, closed=None),
        ),
        (
            {"name": "Tiefbiwak", "capacity": CapacitySchema(open=20, closed=None), "elevation": 2000.0},
            HutTypeSchema(open=HutTypeEnum.selfhut, closed=None),
        ),
    ],
)
def test_guess_hut_type(params: dict[str, Any], expected: HutTypeSchema) -> None:
    ht = guess_hut_type(**params)
    assert (
        ht.if_open == expected.if_open
    ), f"[{params.get('name')}] open hut type '{ht.if_open}' not as expected '{expected.if_open}'"
    assert (
        ht.if_closed == expected.if_closed
    ), f"[{params.get('name')}] closed hut type '{ht.if_closed}' not as expected '{expected.if_closed}'"


# params: max_length, min_length
@pytest.mark.parametrize(
    "name, params,exp_slug",
    [
        ("Neuste Hütte", {}, "neuste"),
        ("Waldhaus-", {}, "waldhaus"),
        ("I`am a very Long hut name", {"max_length": 15}, "very-long-hut"),
        ("i go to shor t be a wo rd", {}, "i-go-to-shor-t-be-a-wo-rd"),
        ("Name2 with 3numbers5", {}, "name-with-numbers"),
    ],
)
def test_guess_slug(name: str, params: dict[str, Any], exp_slug: str) -> None:
    slug = guess_slug_name(name, **params)
    assert slug == exp_slug, f"Slug not as expcted (name: '{name}')."
