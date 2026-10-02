"""Camptocamp.org schema for hut data."""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, computed_field
from pyproj import Transformer

from hut_services import (
    AnswerEnum,
    AuthorSchema,
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    CapacitySchema,
    ContactSchema,
    HutTypeEnum,
    HutTypeSchema,
    LicenseSchema,
    LocationEleSchema,
    OpenMonthlySchema,
    OwnerSchema,
    PhotoSchema,
    SourceDataSchema,
    SourcePropertiesSchema,
    SourceSchema,
    TranslationSchema,
)
from hut_services.core.guess import guess_hut_type

from .open_period import parse_open_months
from .utils import get_images

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
        try:
            geom_data = json.loads(self.geometry.geom)
            if geom_data.get("type") == "Point" and "coordinates" in geom_data:
                coords = geom_data["coordinates"]
                # Coordinates should already be converted to WGS84 by the service
                # If not, they're in Web Mercator (EPSG:3857)
                lon = coords[0]
                lat = coords[1]

                # Check if coordinates are still in Web Mercator (values too large for lat/lon)
                if abs(lat) > 90 or abs(lon) > 180:
                    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                    lon, lat = transformer.transform(lon, lat)
                    logger.debug(f"Converted Web Mercator coordinates for document {self.document_id}")

                return LocationEleSchema(lon=lon, lat=lat, ele=self.elevation)
        except (json.JSONDecodeError, KeyError, IndexError):
            logger.exception(f"Failed to parse geometry for document {self.document_id}")

        logger.warning(f"No usable coordinates for document {self.document_id}")
        return LocationEleSchema(lat=0, lon=0, ele=self.elevation)

    def get_locale(self, lang: str) -> CamptocampLocale | None:
        """Get locale for specific language."""
        for locale in self.locales:
            if locale.lang == lang:
                return locale
        return None

    def get_image_ids(self) -> list[int]:
        """Get image document ids from the associated images."""
        if not self.associations:
            return []
        images = self.associations.get("images", [])
        if not isinstance(images, list):
            return []
        return [img["document_id"] for img in images if isinstance(img, dict) and "document_id" in img]


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
        # Only include languages supported by TranslationSchema (de, en, fr, it)
        lang_mapping = {
            "fr": "fr",
            "de": "de",
            "en": "en",
            "it": "it",
        }

        matched = False
        for locale in self.source_data.locales:
            if locale.lang in lang_mapping:
                setattr(trans, lang_mapping[locale.lang], locale.title)
                matched = True

        if not matched:
            # Keep the original name even if its language is not supported (de, en, fr, it),
            # same convention as the osm/wikidata converters.
            original = self.source_data.get_name()
            if original:
                trans.de = original

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
        }

        for locale in self.source_data.locales:
            if locale.lang in lang_mapping and locale.description:
                setattr(trans, lang_mapping[locale.lang], locale.description)
            elif locale.lang in lang_mapping and locale.summary:
                setattr(trans, lang_mapping[locale.lang], locale.summary)

        if not (trans.de or trans.en or trans.fr or trans.it):
            # Keep the original description even if its language is not supported (de, en, fr, it).
            for locale in self.source_data.locales:
                text = locale.description or locale.summary
                if text:
                    trans.de = text
                    break

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
        """Get photos associated with this hut from camptocamp.org."""
        if self.include_photos is False:
            return []
        return get_images(tuple(self.source_data.get_image_ids()))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Hut website if available (the camptocamp page link is in `source`)."""
        return self.source_data.url or ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capacity(self) -> CapacitySchema:
        """Get capacity information.

        Camptocamp's `capacity` is the unstaffed (winter room) number and
        `capacity_staffed` the staffed one: only huts with a staffed capacity
        have a second, smaller number for the closed season.
        """
        if self.source_data.capacity_staffed is not None:
            return CapacitySchema(open=self.source_data.capacity_staffed, closed=self.source_data.capacity)
        return CapacitySchema(open=self.source_data.capacity)

    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def hut_type(self) -> HutTypeSchema:
        """Guess hut type based on waypoint_type and other info."""
        waypoint_type = self.source_data.waypoint_type or "hut"

        if waypoint_type in ("bivouac", "gite"):
            # camptocamp's 'bivouac' and 'gite' are authoritative:
            # do not let the name/elevation heuristics override them.
            authoritative = {"bivouac": HutTypeEnum.bivouac, "gite": HutTypeEnum.bhotel}
            hut_type = HutTypeSchema(open=authoritative[waypoint_type])
        else:
            # Map Camptocamp types to OSM-like tags for better type detection
            osm_tag_map = {
                "hut": "alpine_hut",
                "gite": "hostel",
                "shelter": "shelter",
                "camp_site": "camp_site",
                "base_camp": "alpine_hut",
            }
            osm_tag = osm_tag_map.get(waypoint_type, "")

            # Determine default based on waypoint type
            default_map = {
                "gite": HutTypeEnum.hostel,
                "shelter": HutTypeEnum.shelter,
                "camp_site": HutTypeEnum.camping,
                "base_camp": HutTypeEnum.hut,
            }
            default_type = default_map.get(waypoint_type, HutTypeEnum.hut)

            hut_type = guess_hut_type(
                name=self.name.i18n or "",
                default=default_type,
                capacity=self.capacity,
                elevation=self.location.ele,
                operator=None,  # Camptocamp doesn't provide SAC/DAV operator info
                osm_tag=osm_tag,
            )

        # A hut that is only open part of the year needs a reduced (closed) type for the rest
        # of the year: 'closed' when camptocamp says it is only accessible when wardened, or for
        # hotel-like types that simply close off-season; otherwise the type guessed from the
        # smaller winter capacity, and 'unknown' if there is no second capacity number.
        if hut_type.if_closed is None:
            if self.source_data.custodianship == "accessible_when_wardened":
                # 'gardé, fermé hors gardiennage': closed outside the warden season.
                hut_type.if_closed = HutTypeEnum.closed
            else:
                open_monthly = self.open_monthly
                known_months = [m for m in range(1, 13) if open_monthly[m] != AnswerEnum.unknown]
                seasonal = 0 < len(known_months) < 12
                if seasonal and hut_type.if_open in (HutTypeEnum.bhotel, HutTypeEnum.hostel, HutTypeEnum.hotel):
                    hut_type.if_closed = HutTypeEnum.closed
                elif seasonal:
                    hut_type.if_closed = HutTypeEnum.unknown
        return hut_type

    @computed_field  # type: ignore[prop-decorator]
    @property
    def open_monthly(self) -> OpenMonthlySchema:
        """Opening months parsed from the (free text) access period."""
        months: dict[int, AnswerEnum] = {}
        for locale in self.source_data.locales:
            if locale.access_period:
                months = parse_open_months(locale.access_period)
                if months:
                    break
        data: dict[str, Any] = {"url": f"https://www.camptocamp.org/waypoints/{self.source_data.document_id}"}
        data.update({f"month_{month:02d}": value for month, value in months.items()})
        return OpenMonthlySchema(**data)

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
            # Truncate phone number to max 30 characters (ContactSchema constraint)
            phone_truncated = phone[:30] if len(phone) > 30 else phone
            return [ContactSchema(phone=phone_truncated)]
        return []
