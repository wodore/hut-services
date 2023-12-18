from pydantic import BaseModel  # , Field


class TranslationSchema(BaseModel):
    """Field with different translations.

    Attributes:
        de: German
        en: English
        fr: French
    """

    de: str = ""
    en: str = ""
    fr: str = ""
    it: str = ""

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
