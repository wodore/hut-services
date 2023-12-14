from typing import Literal, Optional

# from app.models.utils.locale import Translations
# from ..utils.hut_fields import Contact, Monthly, MonthlyOptions, Open, Catering
# from core.db.mixins.timestamp_mixin import TimestampMixinSQLModel
# from typing_extensions import TypedDict
# from .point import Elevation, Latitude, Longitude, Point
# from .point import Point
from geojson_pydantic import Point

# from django.contrib.gis.geos import Point as dbPoint
from pydantic import BaseModel, Field, computed_field

# import phonenumbers
# from app.models.ref import HutRefLink
# from .hut_base import HutBaseSource
from hut_services.core.schema import HutBaseSource
from hut_services.core.schema.locale import TranslationSchema

# from sqlmodel import Field, SQLModel
# from pydantic_computed import Computed, computed
# from ..hut import Hut
# from ..utils.hut_fields import HutType
from .utils import guess_hut_type


class OSMTags(BaseModel):
    tourism: Literal["alpine_hut", "wilderness_hut"]
    wikidata: Optional[str] = None

    name: str
    operator: Optional[str] = None
    email: Optional[str] = None
    contact_email: Optional[str] = Field(None, alias="contact:field")
    phone: Optional[str] = None
    contact_phone: Optional[str] = Field(None, alias="contact:phone")
    website: Optional[str] = None
    contact_website: Optional[str] = Field(None, alias="contact:website")
    note: Optional[str] = None

    bed: Optional[str] = None
    beds: Optional[str] = None
    capacity: Optional[str] = None
    access: Optional[str] = None
    fireplace: Optional[str] = None
    wall: Optional[str] = None
    amenity: Optional[str] = None
    shelter_type: Optional[str] = None
    winter_room: Optional[str] = None
    reservation: Optional[str] = None

    # ele: Optional[Elevation]
    ele: Optional[float] = None


class HutOsm(BaseModel):
    """data from OSM database"""

    # model_config = ConfigDict(populate_by_name=True)

    # source_class: str = Field(default_factory=lambda: __class__.__name__)
    # convert_class: str = Field(default_factory=lambda: __class__.__name__.replace("Source", "Convert"))

    osm_type: Optional[Literal["node", "way", "area"]] = None
    id: int  # TODO: use different name and set in Field
    lat: float | None = None
    lon: float | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    # lat: Optional[Latitude]
    # lon: Optional[Longitude]
    # center_lat: Optional[Latitude]
    # center_lon: Optional[Longitude]
    tags: OSMTags

    def get_id(self) -> str:
        return str(self.id)

    def get_name(self) -> str:
        return self.tags.name

    def get_point(self) -> Point:
        if self.lat:
            return Point(coordinates=(self.lat, self.lon), type="Point")
        elif self.center_lat:
            return Point(coordinates=(self.center_lat, self.center_lon), type="Point")
        else:
            msg = "OSM coordinates are missing."
            raise UserWarning(msg)

    # def get_db_point(self) -> dbPoint:
    #    return self.get_point().db

    # def get_hut(self, include_refs: bool = True) -> Hut:
    #    # _convert = HutOsm0Convert(**self.dict())
    #    _convert = HutOsm0Convert.from_orm(self)
    #    hut = Hut.from_orm(_convert)
    #    if include_refs:
    #        refs = [
    #            HutRefLink(slug="osm", id=self.get_id(), props={"object_type": self.osm_type}, source_data=self.dict())
    #        ]
    #        if self.tags.wikidata:
    #            refs.append(HutRefLink(slug="wikidata", id=self.tags.wikidata))
    #        hut.refs = refs
    #    return hut

    # @classmethod
    # def get_printable_fields(cls, alias=False):
    #    properties = ["osm_type"] + [f"tags.{k}" for k in list(OSMTags.__fields__.keys())]
    #    return properties


HutOsmSource = HutBaseSource[HutOsm]


class HutOsm0Convert(BaseModel):
    source: HutOsm

    @property
    def _tags(self) -> OSMTags:
        return self.source.tags

    @computed_field
    @property
    def name(self) -> dict[str, str]:
        return TranslationSchema(de=self._tags.name[:69]).model_dump()

    @computed_field
    @property
    def description(self) -> dict[str, str]:
        return TranslationSchema(en=self._tags.note or "").model_dump()

    @computed_field
    @property
    def note(self) -> dict[str, str]:
        return self.description

    @computed_field
    @property
    def point(self) -> Point:
        lat = self.source.lat or self.source.center_lat
        lon = self.source.lon or self.source.center_lon
        if not (lat and lon):
            msg = f"OSM coordinates are missing: {self._tags.name} (#{self.source.id})"
            raise UserWarning(msg)
        return Point(lat=lat, lon=lon)

    @computed_field
    @property
    def url(self) -> str:
        url = ""
        if self._tags.website:
            url = self._tags.website
        elif self._tags.contact_website:
            url = self._tags.contact_website
        if len(url) > 200:
            url = ""
        return url

    @computed_field
    @property
    def elevation(self) -> float | None:
        if self._tags.ele:
            return self._tags.ele
        else:
            return None

    @computed_field
    @property
    def capacity(self) -> Optional[int]:
        tags = self._tags
        cap = None
        if tags.capacity:
            cap = tags.capacity
        elif tags.beds:
            cap = tags.beds
        elif tags.bed:
            cap = tags.bed
        try:
            if cap is not None:
                cap = int(cap)
        except ValueError:
            cap = None
        return cap

    @computed_field
    @property
    def capacity_shelter(self) -> Optional[int]:
        if self._tags.winter_room:
            try:
                return int(self._tags.winter_room)  # capacity in tag
            except ValueError:
                pass
        if self._tags.tourism == "wilderness_hut":
            return self.capacity
        return None

    @computed_field
    @property
    def type(self) -> str:
        """Returns type slug"""
        _orgs = ""
        if self._tags.operator:
            _orgs = "sac" if "sac" in self._tags.operator else ""
        return guess_hut_type(
            name=self.name.get("de", ""),
            capacity=self.capacity,
            capacity_shelter=self.capacity_shelter,
            elevation=self.elevation,
            organization=_orgs,
            osm_tag=self._tags.tourism,
        )

    @computed_field
    @property
    def owner(self) -> str:
        owner = self._tags.operator or ""
        # if owner:
        #    if len(owner) > 100:
        #        click.secho(f"warning: owner too long: '{owner}'", fg="red")
        #    owner = owner[:100]
        return owner

    @computed_field
    @property
    def is_active(self) -> bool:
        if self._tags.access:
            return self._tags.access in ["yes", "public", "customers", "permissive"]
        return True

    @computed_field
    @property
    def props(self) -> dict[str, str]:
        return {"osm_type": self.source.osm_type or "node"}
