from typing import Annotated

from pydantic import BaseModel  # , Field
from pydantic.functional_validators import BeforeValidator


def none_to_str(v: str | None) -> str:
    """Convert a `None` to an empty string."""
    if v is None:
        return ""
    return v


NoneStr = Annotated[str, BeforeValidator(none_to_str)]


class TranslationSchema(BaseModel):
    """Field with different translations.

    Attributes:
        de: German
        en: English
        fr: French
    """

    de: NoneStr = ""
    en: NoneStr = ""
    fr: NoneStr = ""
    it: NoneStr = ""

    @property
    def i18n(self) -> str:
        """Returns the first stored translation in the following order:
        `de`, `en`, `fr` or `it`.
        """
        _codes: tuple = ("de", "en", "fr", "it")
        for code in _codes:
            if getattr(self, code, None):
                return str(getattr(self, code))
        return ""
