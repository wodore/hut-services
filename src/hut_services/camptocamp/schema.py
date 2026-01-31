"""Camptocamp.org schema for hut data."""

import logging
from typing import Any

from pydantic import BaseModel, Field, computed_field

from hut_services import (
    AuthorSchema,
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    CapacitySchema,
    ContactSchema,
    HutTypeEnum,
    HutTypeSchema,
    LicenseSchema,
    LocationEleSchema,
    OwnerSchema,
    PhotoSchema,
    SourceDataSchema,
    SourcePropertiesSchema,
    SourceSchema,
    TranslationSchema,
)
from hut_services.core.guess import guess_hut_type

logger = logging.getLogger(__name__)


class CamptocampLocale(BaseModel):
    """Camptocamp locale data."""

    version: int | None = None
    lang: str
    title: str
    summary: str | None = None
    description: str | None = None
    access: str | None = None
    access_period: str | None = None


class CamptocampGeometry(BaseModel):
    """Camptocamp geometry data."""

    version: int
    geom: str  # GeoJSON string


class CamptocampArea(BaseModel):
    """Camptocamp area data."""

    document_id: int
    version: int
    locales: list[CamptocampLocale]
    area_type: str
    available_langs: list[str] | None = None
    protected: bool = False
    type: str = "a"


class CamptocampDocument(SourceDataSchema):
    """Camptocamp document/hut data model."""

    document_id: int
    version: int
    locales: list[CamptocampLocale]
    geometry: CamptocampGeometry
    quality: str | None = None
    waypoint_type: str | None = None
    elevation: int | None = None
    available_langs: list[str] | None = None
    areas: list[CamptocampArea] = Field(default_factory=list)
    protected: bool = False
    type: str | None = "w"

    # Additional optional fields from detailed API
    capacity: int | None = None
    capacity_staffed: int | None = None
    phone: str | None = None
    phone_custodian: str | None = None
    url: str | None = None
    custodian: str | None = None
    custodianship: str | None = None
    matress_unstaffed: bool | None = None
    blanket_unstaffed: bool | None = None
    gas_unstaffed: bool | None = None
    heating_unstaffed: bool | None = None
    associations: dict[str, Any] | None = None

    def get_id(self) -> str:
        """Get the document ID as string."""
        return str(self.document_id)

    def get_name(self) -> str:
        """Get the name from the first locale."""
        if self.locales:
            return self.locales[0].title
        return ""

    def get_location(self) -> LocationEleSchema:
        """Extract location from geometry."""
        import json

        try:
            geom_data = json.loads(self.geometry.geom)
            if geom_data.get("type") == "Point" and "coordinates" in geom_data:
                coords = geom_data["coordinates"]
                # Coordinates should already be converted to WGS84 by the service
                # If not, they're in Web Mercator (EPSG:3857)
                lon = coords[0]
                lat = coords[1]

                # Check if coordinates seem to be in Web Mercator (values too large for lat/lon)
                if abs(lat) > 90 or abs(lon) > 180:
                    # Need conversion but don't have pyproj here
                    logger.warning(f"Coordinates appear to be in projected system for document {self.document_id}")
                    return LocationEleSchema(lon=None, lat=None, ele=self.elevation)

                return LocationEleSchema(lon=lon, lat=lat, ele=self.elevation)
        except (json.JSONDecodeError, KeyError, IndexError):
            logger.exception(f"Failed to parse geometry for document {self.document_id}")

        return LocationEleSchema(lon=None, lat=None, ele=self.elevation)

    def get_locale(self, lang: str) -> CamptocampLocale | None:
        """Get locale for specific language."""
        for locale in self.locales:
            if locale.lang == lang:
                return locale
        return None


class CamptocampProperties(SourcePropertiesSchema):
    """Properties saved together with the source data."""

    quality: str = Field(..., description="Quality indicator from camptocamp")
    waypoint_type: str = Field(default="hut", description="Waypoint type from camptocamp")


class CamptocampHutSource(BaseHutSourceSchema[CamptocampDocument, CamptocampProperties]):
    """Data from camptocamp.org database."""

    source_name: str = "camptocamp"


class CamptocampApiResponse(BaseModel):
    """Response from camptocamp API."""

    documents: list[CamptocampDocument]
    total: int | None = None


class CamptocampHut0Convert(BaseHutConverterSchema[CamptocampDocument]):
    """Convert Camptocamp data to HutSchema."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> TranslationSchema:
        """Get name with translations."""
        trans = TranslationSchema()

        # Map camptocamp language codes to our schema
        lang_mapping = {
            "fr": "fr",
            "de": "de",
            "en": "en",
            "it": "it",
            "es": "es",
            "ca": "ca",
            "eu": "eu",
            "zh": "zh",
            "sl": "sl",
        }

        for locale in self.source_data.locales:
            if locale.lang in lang_mapping:
                setattr(trans, lang_mapping[locale.lang], locale.title)

        # i18n is automatically computed by TranslationSchema property
        # It returns the first available translation in order: de, en, fr, it

        return trans

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_name(self) -> str:
        return "camptocamp"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> TranslationSchema:
        """Get description with translations."""
        trans = TranslationSchema()

        lang_mapping = {
            "fr": "fr",
            "de": "de",
            "en": "en",
            "it": "it",
            "es": "es",
            "ca": "ca",
            "eu": "eu",
            "zh": "zh",
            "sl": "sl",
        }

        for locale in self.source_data.locales:
            if locale.lang in lang_mapping and locale.description:
                setattr(trans, lang_mapping[locale.lang], locale.description)
            elif locale.lang in lang_mapping and locale.summary:
                setattr(trans, lang_mapping[locale.lang], locale.summary)

        return trans

    @computed_field  # type: ignore[prop-decorator]
    @property
    def author(self) -> AuthorSchema | None:
        """Get author information."""
        if self.description.i18n or self.description.fr or self.description.en:
            return AuthorSchema(name="Camptocamp contributors", url="https://www.camptocamp.org")
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> SourceSchema | None:
        """Get source information."""
        return SourceSchema(
            name=self.source_name,
            ident=self.source_data.get_id(),
            url=f"https://www.camptocamp.org/waypoints/{self.source_data.document_id}",
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def license(self) -> LicenseSchema | None:
        """Get license information."""
        return LicenseSchema(
            slug="cc-by-sa-4.0", name="CC BY-SA 4.0", url="https://creativecommons.org/licenses/by-sa/4.0/"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def notes(self) -> list[TranslationSchema]:
        """Get notes including access and period information."""
        notes = []

        # Add access information
        for locale in self.source_data.locales:
            if locale.access:
                note = TranslationSchema()
                if locale.lang == "fr":
                    note.fr = f"Accès: {locale.access}"
                elif locale.lang == "en":
                    note.en = f"Access: {locale.access}"
                elif locale.lang == "de":
                    note.de = f"Zugang: {locale.access}"
                elif locale.lang == "it":
                    note.it = f"Accesso: {locale.access}"

                if note.fr or note.en or note.de or note.it:
                    notes.append(note)
                    break

        # Add access period information
        for locale in self.source_data.locales:
            if locale.access_period:
                note = TranslationSchema()
                if locale.lang == "fr":
                    note.fr = locale.access_period
                elif locale.lang == "en":
                    note.en = locale.access_period
                elif locale.lang == "de":
                    note.de = locale.access_period
                elif locale.lang == "it":
                    note.it = locale.access_period

                if note.fr or note.en or note.de or note.it:
                    notes.append(note)
                    break

        # Add equipment notes
        equipment_notes = []
        if self.source_data.matress_unstaffed:
            equipment_notes.append("matelas/mattresses")
        if self.source_data.blanket_unstaffed:
            equipment_notes.append("couvertures/blankets")

        if equipment_notes:
            notes.append(
                TranslationSchema(
                    fr=f"Équipement disponible: {', '.join(equipment_notes)}",
                    en=f"Available equipment: {', '.join(equipment_notes)}",
                )
            )

        return notes

    @computed_field  # type: ignore[prop-decorator]
    @property
    def owner(self) -> OwnerSchema | None:
        """Get owner information."""
        # Use custodian field if available, or derive from custodianship
        if self.source_data.custodian:
            return OwnerSchema(name=self.source_data.custodian)
        elif self.source_data.custodianship and self.source_data.custodianship != "no_warden":
            # Capitalize and format custodianship type
            custodian_type = self.source_data.custodianship.replace("_", " ").title()
            return OwnerSchema(name=custodian_type)
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def photos(self) -> list[PhotoSchema]:
        """Get photos - to be implemented with image API."""
        # TODO: Implement fetching photos from camptocamp API
        # The API endpoint would be something like:
        # https://api.camptocamp.org/images?w={document_id}
        return []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Get URL if available."""
        if hasattr(self.source_data, "url") and self.source_data.url:
            return self.source_data.url
        return f"https://www.camptocamp.org/waypoints/{self.source_data.document_id}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capacity(self) -> CapacitySchema:
        """Get capacity information."""
        # Use the capacity field directly if available
        capacity_open = self.source_data.capacity
        capacity_staffed = self.source_data.capacity_staffed

        return CapacitySchema(open=capacity_open, closed=capacity_staffed)

    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def hut_type(self) -> HutTypeSchema:
        """Guess hut type based on waypoint_type and other info."""
        default_type = HutTypeEnum.hut  # Default to hut

        # Could potentially use waypoint_type or other fields to determine
        # For now, use the guess function
        return guess_hut_type(
            name=self.name.i18n or "",
            default=default_type,
            capacity=self.capacity,
            elevation=self.location.ele,
            operator=None,  # Camptocamp doesn't provide SAC/DAV operator info
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_public(self) -> bool:
        """Determine if hut is public."""
        # Assume all huts from camptocamp are public
        return True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def contacts(self) -> list[ContactSchema]:
        """Get contact information."""
        phone = self.source_data.phone or self.source_data.phone_custodian
        if phone:
            return [ContactSchema(phone=phone)]
        return []
