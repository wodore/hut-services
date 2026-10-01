"""Tests for the access_period free-text parser (offline)."""

from hut_services.camptocamp.open_period import parse_open_months


def _m(txt: str) -> dict[int, str]:
    return {m: str(v.value) for m, v in sorted(parse_open_months(txt).items())}


def test_range_with_edge_qualifiers() -> None:
    """The real Hollandiahütte access period."""
    assert _m("Mi-mars à fin mai et juillet à début septembre") == {
        3: "yesish",
        4: "yes",
        5: "yes",
        7: "yes",
        8: "yes",
        9: "yesish",
    }


def test_simple_range_french() -> None:
    assert _m("de juin à septembre") == {6: "yes", 7: "yes", 8: "yes", 9: "yes"}


def test_wrap_around_german() -> None:
    assert _m("November bis März") == {11: "yes", 12: "yes", 1: "yes", 2: "yes", 3: "yes"}


def test_all_year() -> None:
    assert _m("Toute l'année") == {m: "yes" for m in range(1, 13)}
    assert _m("ganzjährig geöffnet") == {m: "yes" for m in range(1, 13)}


def test_single_month() -> None:
    assert _m("juillet") == {7: "yes"}


def test_season_only() -> None:
    assert _m("ouvert en été") == {6: "yesish", 7: "yesish", 8: "yesish", 9: "yesish"}


def test_compound_ranges() -> None:
    assert _m("mi-juin à fin septembre et de fin décembre à avril") == {
        1: "yes",
        2: "yes",
        3: "yes",
        4: "yes",
        6: "yesish",
        7: "yes",
        8: "yes",
        9: "yes",
        12: "maybe",
    }


def test_unparseable_stays_empty() -> None:
    assert _m("ouvert sur réservation") == {}
    assert _m("") == {}
