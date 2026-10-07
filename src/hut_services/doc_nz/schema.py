"""Schemas for the New Zealand Department of Conservation (DOC) hut source.

Base data comes from the official "DOC Huts" open-data layer
(ArcGIS FeatureServer, CC-BY 4.0, no authentication):
<https://doc-deptconservation.opendata.arcgis.com/maps/doc-huts>

Optional detail enrichment (bunk counts, hut category, introduction, status)
comes from the official DOC API v2 (`/v2/huts/{id}/detail`), which needs a
free API key from <https://api.doc.govt.nz>.
"""

import logging
import typing as t
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, BeforeValidator, Field, computed_field

from hut_services import (
    AuthorSchema,
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    CapacitySchema,
    HutTypeEnum,
    HutTypeSchema,
    LicenseSchema,
    OwnerSchema,
    SourceDataSchema,
    SourcePropertiesSchema,
    SourceSchema,
    TranslationSchema,
)
from hut_services.core.guess import guess_hut_type
from hut_services.core.schema.geo import LocationEleSchema

logger = logging.getLogger(__name__)


def _yes_no_to_bool(value: str | bool | None) -> bool | None:
    """Convert the layer's `"Yes"`/`"No"` strings (and the API's booleans) to `bool`."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return value.strip().lower() == "yes"


def _split_facilities(value: str | list[str] | None) -> list[str] | None:
    """The layer stores facilities as one comma separated string, the API as a list."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    return [f.strip() for f in value.split(",") if f.strip()]


def _epoch_ms_to_datetime(value: float | int | str | datetime | None) -> datetime | None:
    """Convert ArcGIS epoch milliseconds to a UTC datetime (datetime passes through)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


YesNoBool: t.TypeAlias = t.Annotated[bool | None, BeforeValidator(_yes_no_to_bool)]
FacilitiesList: t.TypeAlias = t.Annotated[list[str] | None, BeforeValidator(_split_facilities)]
EpochMs: t.TypeAlias = t.Annotated[datetime | None, BeforeValidator(_epoch_ms_to_datetime)]


class DocNzHutSchema(SourceDataSchema):
    """One hut from the DOC NZ `DOC Huts` open-data layer, optionally
    enriched with fields from the official DOC API v2 detail endpoint."""

    # open-data layer (FeatureServer attributes)
    asset_id: int = Field(..., alias="assetId")
    name: str
    place: str | None = None
    region: str | None = None
    bookable: YesNoBool = None
    facilities: FacilitiesList = None
    has_alerts: str | None = Field(None, alias="hasAlerts")
    introduction_thumbnail: str | None = Field(None, alias="introductionThumbnail")
    static_link: str | None = Field(None, alias="staticLink")
    location_string: str | None = Field(None, alias="locationString")
    object_id: int | None = Field(None, alias="OBJECTID")
    global_id: str | None = Field(None, alias="GlobalID")
    date_loaded: EpochMs = Field(None, alias="dateLoadedToGIS")
    # enrichment (DOC API v2 `/huts/{id}/detail`, requires API key)
    number_of_bunks: int | None = Field(None, alias="numberOfBunks")
    hut_category: str | None = Field(None, alias="hutCategory")
    proximity_to_road_end: str | None = Field(None, alias="proximityToRoadEnd")
    introduction: str | None = None
    status: str | None = None
    # geometry, WGS84 (requested with `outSR=4326`)
    lat: float
    lon: float

    def get_id(self) -> str:
        """DOC `assetId` as string."""
        return str(self.asset_id)

    def get_name(self) -> str:
        return self.name.strip()

    def get_location(self) -> LocationEleSchema:
        return LocationEleSchema(lat=self.lat, lon=self.lon, ele=None)


class DocNzDetailSchema(BaseModel):
    """Fields of the DOC API v2 `/huts/{id}/detail` response used for enrichment."""

    number_of_bunks: int | None = Field(None, alias="numberOfBunks")
    hut_category: str | None = Field(None, alias="hutCategory")
    proximity_to_road_end: str | None = Field(None, alias="proximityToRoadEnd")
    introduction: str | None = None
    status: str | None = None


class DocNzAlertSchema(BaseModel):
    """One alert from the DOC API v2 `/huts/alerts` endpoints."""

    display_date: str | None = Field(None, alias="displayDate")
    heading: str | None = None
    detail: str | None = None


class DocNzHutAlerts(BaseModel):
    """Alerts for one hut from the DOC API v2 `/huts/alerts` endpoints."""

    asset_id: int = Field(..., alias="assetId")
    name: str = ""
    alerts: list[DocNzAlertSchema] = Field(default_factory=list)


class DocNzProperties(SourcePropertiesSchema):
    """Properties saved together with the source data."""

    bookable: bool | None = Field(None, description="hut can be booked through DOC's online booking system")
    region: str | None = Field(None, description="DOC region name")
    place: str | None = Field(None, description="place / conservation area name")
    hut_category: str | None = Field(None, description="hut category by DOC (e.g. 'Serviced', 'Basic')")


class DocNzHutSource(BaseHutSourceSchema[DocNzHutSchema, DocNzProperties]):
    """Data from the DOC NZ open-data layer."""

    source_name: str = "doc_nz"


class HutCategoryEnum(str, Enum):
    """Hut categories used by DOC."""

    great_walk = "great_walk"
    serviced = "serviced"
    standard = "standard"
    basic = "basic"
    bivvy = "bivvy"
    unknown = "unknown"


DOC_NZ_CATEGORY_TYPES: dict[HutCategoryEnum, HutTypeEnum] = {
    HutCategoryEnum.great_walk: HutTypeEnum.hut,  # attended (wardens), bookable
    HutCategoryEnum.serviced: HutTypeEnum.hut,  # attended
    HutCategoryEnum.standard: HutTypeEnum.selfhut,  # unattended
    HutCategoryEnum.basic: HutTypeEnum.selfhut,  # unattended, minimal
    HutCategoryEnum.bivvy: HutTypeEnum.bivouac,
    HutCategoryEnum.unknown: HutTypeEnum.unknown,
}

DOC_NZ_LICENSE = LicenseSchema(
    slug="CC-BY-4.0",
    url="https://creativecommons.org/licenses/by/4.0/",
    name="Creative Commons Attribution 4.0 International",
)
"""DOC publishes its open spatial data (incl. the DOC Huts layer) under CC-BY 4.0."""

DOC_NZ_OWNER = OwnerSchema(slug="", name="Department of Conservation Te Papa Atawhai", url="https://www.doc.govt.nz")

DOC_NZ_AUTHOR = AuthorSchema(name="Department of Conservation Te Papa Atawhai", url="https://www.doc.govt.nz")


def get_hut_category(category: str | None) -> HutCategoryEnum:
    """Map a DOC hut category string to [`HutCategoryEnum`][...].

    Observed API vocabulary: `"Great Walk"`, `"Serviced"`, `"Standard"`,
    `"Basic/bivvies"` (one combined category — bivs stay `selfhut`, the
    model's `bivouac` implies altitude which NZ bivs do not have).
    """
    if not category:
        return HutCategoryEnum.unknown
    cat = category.strip().lower()
    if "great walk" in cat:
        return HutCategoryEnum.great_walk
    if "serviced" in cat:
        return HutCategoryEnum.serviced
    if "standard" in cat:
        return HutCategoryEnum.standard
    if cat.startswith("biv") or "bivouac" in cat:  # standalone bivvy category, NOT "Basic/bivvies"
        return HutCategoryEnum.bivvy
    if "basic" in cat:
        return HutCategoryEnum.basic
    return HutCategoryEnum.unknown


class DocNzHut0Convert(BaseHutConverterSchema[DocNzHutSchema]):
    """Converter for the DOC NZ source (version 0)."""

    include_photos: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(en=self.source_data.get_name())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_name(self) -> str:
        return "doc_nz"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> TranslationSchema:
        introduction = self.source_data.introduction
        if introduction:
            return TranslationSchema(en=introduction)
        return TranslationSchema()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def author(self) -> AuthorSchema | None:
        if self.source_data.introduction:
            return DOC_NZ_AUTHOR
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> SourceSchema | None:
        return SourceSchema(
            name=self.source_name,
            ident=self.source_data.get_id(),
            url=self.source_data.static_link,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def license(self) -> LicenseSchema | None:
        return DOC_NZ_LICENSE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def owner(self) -> OwnerSchema | None:
        return DOC_NZ_OWNER

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return self.source_data.static_link or ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def country_code(self) -> str | None:
        return "nz"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capacity(self) -> CapacitySchema:
        return CapacitySchema(open=self.source_data.number_of_bunks, closed=None)

    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def hut_type(self) -> HutTypeSchema:
        category = get_hut_category(self.source_data.hut_category)
        default = DOC_NZ_CATEGORY_TYPES[category]
        attended = category in (HutCategoryEnum.great_walk, HutCategoryEnum.serviced)
        return guess_hut_type(
            name=self.name.i18n,
            default=default,
            capacity=self.capacity,
            elevation=self.source_data.get_location().ele,
            attended=attended,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_active(self) -> bool:
        status = self.source_data.status
        if status is None:
            return True
        return status.strip().lower() not in ("closed", "removed", "destroyed")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def extras(self) -> dict[str, t.Any]:
        """DOC specific fields: `region`, `place`, `hut_category`, `bookable`,
        `facilities`, `proximity_to_road_end`, `status`, `introduction_thumbnail`.
        `bookable` is a static flag (booking itself runs on bookings.doc.govt.nz,
        see <https://www.doc.govt.nz/parks-and-recreation/places-to-go/online-bookings/>)."""
        extra: dict[str, t.Any] = {}
        if self.source_data.region:
            extra["region"] = self.source_data.region
        if self.source_data.place:
            extra["place"] = self.source_data.place
        if self.source_data.hut_category:
            extra["hut_category"] = self.source_data.hut_category
        if self.source_data.bookable is not None:
            extra["bookable"] = self.source_data.bookable
        if self.source_data.facilities:
            extra["facilities"] = self.source_data.facilities
        if self.source_data.proximity_to_road_end:
            extra["proximity_to_road_end"] = self.source_data.proximity_to_road_end
        if self.source_data.status:
            extra["status"] = self.source_data.status
        if self.source_data.introduction_thumbnail:
            extra["introduction_thumbnail"] = self.source_data.introduction_thumbnail
        return extra
