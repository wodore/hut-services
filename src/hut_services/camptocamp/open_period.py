"""Parse opening months from camptocamp's free text ``access_period`` field.

Camptocamp has no structured opening data; the information is only available
as localized free text like ``"Mi-mars à fin mai et juillet à début septembre"``.
This module extracts month ranges from the common French, German, English and
Italian phrasings into [`AnswerEnum`][hut_services.core.schema.AnswerEnum]
values for [`OpenMonthlySchema`][hut_services.core.schema.OpenMonthlySchema].

Heuristics, deliberately conservative:
- months fully inside a range -> ``yes``
- range edges qualified with mid/early (mi, début, early, Mitte, ...) -> ``yesish``
- range start qualified with late (fin, late, Ende, ...) -> ``maybe``
- anything unparseable stays ``unknown`` (the converter default)
"""

import re
import unicodedata

from hut_services.core.schema import AnswerEnum

_MONTHS: dict[int, list[str]] = {
    1: ["janvier", "januar", "january", "gennaio", "jan", "gen"],
    2: ["fevrier", "februar", "february", "febbraio", "fev", "feb"],
    3: ["mars", "marz", "march", "marzo", "mar"],
    4: ["avril", "april", "aprile", "avr", "apr"],
    5: ["mai", "may", "maggio", "mag"],
    6: ["juin", "juni", "june", "giugno", "juin", "jun"],
    7: ["juillet", "juli", "july", "luglio", "juil", "jul"],
    8: ["aout", "august", "agosto", "aug"],
    9: ["septembre", "september", "settembre", "sept", "sep", "set"],
    10: ["octobre", "oktober", "ottobre", "octobre", "oct", "okt", "ott"],
    11: ["novembre", "november", "novembre", "nov"],
    12: ["decembre", "dezember", "december", "dicembre", "dec", "dez", "dic"],
}
_MONTH_WORDS = sorted(((w, m) for m, ws in _MONTHS.items() for w in ws), key=lambda e: -len(e[0]))
_MONTH_RE = re.compile(r"\b(" + "|".join(w for w, _ in _MONTH_WORDS) + r")\b")

# modifiers directly before a month word: mid/early-ish and late-ish
_SOFT = "debut|early|anfang|inizio|principio|mid|mitte|meta|mi"
_LATE = "fin|late|ende|fine|fondo"
_MODIFIER_RE = re.compile(r"(?:^|\W)(" + _SOFT + "|" + _LATE + r")\W*$")

# segment separators: "et", "and", "und", italian "e", ";", ",", "+"
_SEGMENT_RE = re.compile(r"\s(?:et|and|und|e)\s|[;,+]")

_ALL_YEAR = (
    "toute l annee",
    "toute annee",
    "annee",
    "all year",
    "year round",
    "ganzjahrig",
    "ganzes jahr",
    "tutto l anno",
    "sempre",
)
_CLOSED = re.compile(r"\b(fermee?|closed|chiuso|gesperrt)\b")
_SEASON_SUMMER = re.compile(r"\b(ete|summer|sommer|estate)\b")
_SEASON_WINTER = re.compile(r"\b(hiver|winter|inverno)\b")

# preference order when merging segments
_RANK = {AnswerEnum.yes: 5, AnswerEnum.yesish: 4, AnswerEnum.maybe: 3, AnswerEnum.noish: 2, AnswerEnum.no: 1}


def _normalize(text: str) -> str:
    """Lowercase and strip accents."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _month_span(start: int, end: int) -> list[int]:
    """Inclusive month list, handling wrap-around (e.g. November to March)."""
    if start == end:
        return [start]
    if start < end:
        return list(range(start, end + 1))
    return list(range(start, 13)) + list(range(1, end + 1))


def _modifier_before(segment: str, pos: int) -> str | None:
    """Return the qualifier word directly before a month, if any."""
    found = _MODIFIER_RE.search(segment[:pos])
    return found.group(1) if found else None


def _is_late(mod: str | None) -> bool:
    return mod is not None and re.fullmatch(_LATE, mod) is not None


def _parse_segment(segment: str) -> dict[int, AnswerEnum]:
    """Parse one segment like ``mi-mars a fin mai`` or ``juillet``."""
    months = [(m.start(), _MONTH_WORDS_LOOKUP[m.group(1)]) for m in _MONTH_RE.finditer(segment)]
    if not months:
        # season-only segments (no month words)
        if _SEASON_SUMMER.search(segment):
            return {m: AnswerEnum.yesish for m in (6, 7, 8, 9)}
        if _SEASON_WINTER.search(segment):
            return {m: AnswerEnum.yesish for m in (12, 1, 2, 3)}
        return {}
    out: dict[int, AnswerEnum] = {}
    if len(months) == 1:
        pos, m = months[0]
        mod = _modifier_before(segment, pos)
        out[m] = AnswerEnum.maybe if _is_late(mod) else (AnswerEnum.yesish if mod else AnswerEnum.yes)
        return out
    # range: first month ... second month
    (pos1, m1), (pos2, m2) = months[0], months[1]
    mod1, mod2 = _modifier_before(segment, pos1), _modifier_before(segment, pos2)
    for m in _month_span(m1, m2):
        out[m] = AnswerEnum.yes
    if mod1:
        out[m1] = AnswerEnum.maybe if _is_late(mod1) else AnswerEnum.yesish
    if mod2 and not _is_late(mod2):  # until end of month -> stays yes
        out[m2] = AnswerEnum.yesish
    # extra months beyond the range pair are treated as singles
    for pos, m in months[2:]:
        mod = _modifier_before(segment, pos)
        out.setdefault(m, AnswerEnum.maybe if _is_late(mod) else (AnswerEnum.yesish if mod else AnswerEnum.yes))
    return out


_MONTH_WORDS_LOOKUP = dict(_MONTH_WORDS)


def parse_open_months(text: str) -> dict[int, AnswerEnum]:
    """Extract opening months from an ``access_period`` free text.

    Returns a mapping month (1-12) -> answer; unmentioned months are left out.
    """
    if not text:
        return {}
    norm = _normalize(text)
    if any(phrase in norm for phrase in _ALL_YEAR):
        return {m: AnswerEnum.yes for m in range(1, 13)}
    result: dict[int, AnswerEnum] = {}
    for segment in _SEGMENT_RE.split(norm):
        segment = segment.strip()
        if not segment or _CLOSED.search(segment):
            continue
        for month, answer in _parse_segment(segment).items():
            if month not in result or _RANK[answer] > _RANK[result[month]]:
                result[month] = answer
    return result


if __name__ == "__main__":
    demo = "Mi-mars à fin mai et juillet à début septembre"
    print({m: str(v) for m, v in sorted(parse_open_months(demo).items())})
