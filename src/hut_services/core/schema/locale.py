from pydantic import BaseModel


class TranslationSchema(BaseModel):
    de: str = ""
    en: str = ""
    fr: str = ""
    it: str = ""
