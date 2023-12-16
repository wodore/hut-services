from pydantic import BaseModel  # , Field


class TranslationSchema(BaseModel):
    de: str = ""
    en: str = ""
    fr: str = ""
    it: str = ""

    @property
    def i18n(self) -> str:
        _codes: tuple = ("de", "en", "fr", "it")
        for code in _codes:
            if getattr(self, code, None):
                return str(getattr(self, code))
        return ""
