import logging
from enum import Enum
from typing import Literal

from geojson_pydantic import Feature, FeatureCollection, Point
from pydantic import BaseModel, Field, computed_field

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
)
from hut_services.core.guess import guess_hut_type
from hut_services.core.schema._photo import PhotoSchema
from hut_services.core.schema.geo import LocationEleSchema
from hut_services.core.schema.locale import TranslationSchema

from .coordinates import CORRECTIONS
from .utils import get_original_images, refuges_lic

logger = logging.getLogger(__name__)


class HutTypeRefugesEnum(str, Enum):
    missing = "missing"
    cabane_non_gardee = "cabane-non-gardee"
    refuge_garde = "refuge-garde"
    gite_d_etape = "gite-d-etape"
    batiment_en_montagne = "batiment-en-montagne"


REFUGES_HUT_TYPES: dict[int, HutTypeRefugesEnum] = {
    7: HutTypeRefugesEnum.cabane_non_gardee,
    10: HutTypeRefugesEnum.refuge_garde,
    9: HutTypeRefugesEnum.gite_d_etape,
    28: HutTypeRefugesEnum.batiment_en_montagne,
}
WODORE_HUT_TYPES: dict[int, HutTypeEnum] = {
    7: HutTypeEnum.selfhut,
    10: HutTypeEnum.hut,
    9: HutTypeEnum.hut,
    28: HutTypeEnum.bhotel,
}


class RefugesInfoProperties(SourcePropertiesSchema):
    """Properties save together with the source data."""

    slug: str = Field(..., description="hut slug by refuges.info")
    hut_type: HutTypeRefugesEnum = Field(..., description="hut type by refuges.info.")


class _Coord(BaseModel):
    alt: float
    long: float
    lat: float
    precision: dict[str, str]


class _ValeurNom(BaseModel):
    nom: str
    valeur: str | None


class _ValeurID(BaseModel):
    ident: int = Field(..., alias="id")
    valeur: str | None


class _NomID(BaseModel):
    ident: int = Field(..., alias="id")
    nom: str | None


class _Type(_ValeurID):
    icone: str


class _Etat(_ValeurID):
    ident: Literal["ouverture", "fermeture", "cle_a_recuperer", "detruit", "NULL", "null"] | None = Field(
        ..., alias="id"
    )  # type: ignore[assignment]


class _Date(BaseModel):
    derniere_modif: str | None
    creation: str


class _Article(BaseModel):
    demonstratif: str
    defini: str
    partitif: str


class _SiteOfficiel(_ValeurNom):
    url: str | None


class _PlacesMatelas(_ValeurNom):
    nb: int | None


class _InfoComp(BaseModel):
    site_officiel: _SiteOfficiel
    manque_un_mur: _ValeurNom
    cheminee: _ValeurNom
    poele: _ValeurNom
    couvertures: _ValeurNom
    places_matelas: _PlacesMatelas
    latrines: _ValeurNom
    bois: _ValeurNom
    eau: _ValeurNom


class _Description(BaseModel):
    valeur: str


class _RefugesInfoFeatureProperties(BaseModel):
    ident: int = Field(..., alias="id")
    lien: str  # link
    nom: str
    sym: str
    coord: _Coord
    hut_type: _Type = Field(..., alias="type")
    places: _ValeurNom
    etat: _Etat
    date: _Date
    remarque: _ValeurNom
    acces: _ValeurNom
    proprio: _ValeurNom
    createur: _NomID
    article: _Article
    info_comp: _InfoComp
    description: _Description


class RefugesInfoFeature(Feature, SourceDataSchema):
    """RefugesInfo Feature Model with required properties and geometry."""

    geometry: Point
    properties: _RefugesInfoFeatureProperties

    def get_id(self) -> str:
        return str(self.properties.ident)

    def get_name(self) -> str:
        return str(self.properties.nom).strip('"').strip()

    def get_location(self) -> LocationEleSchema:
        # coords = self.geometry.coordinates
        lat: float | None
        lon: float | None
        lat, lon = CORRECTIONS.get(self.properties.ident, (self.properties.coord.lat, self.properties.coord.long))
        return LocationEleSchema(lat=lat, lon=lon, ele=self.properties.coord.alt)

    def get_properties(self) -> RefugesInfoProperties:
        slug = self.properties.lien.split("/")[-2]
        return RefugesInfoProperties(
            hut_type=REFUGES_HUT_TYPES.get(self.properties.hut_type.ident, HutTypeRefugesEnum.missing), slug=slug
        )


class RefugesInfoFeatureCollection(FeatureCollection):
    """Used to get FeatureCollection, not returned by the service."""

    generator: str
    copyright_by: str = Field(..., alias="copyright")
    timestamp: str
    size: str
    features: list[RefugesInfoFeature]


class RefugesInfoHutSource(BaseHutSourceSchema[RefugesInfoFeature, RefugesInfoProperties]):
    """Data from refuges.info database."""

    source_name: str = "refuges"


class RefugesInfoHut0Convert(BaseHutConverterSchema[RefugesInfoFeature]):
    @property
    def _props(self) -> _RefugesInfoFeatureProperties:
        return self.source_data.properties

    ## implemented in base
    # @computed_field  # type: ignore[prop-decorator]
    # @property
    # def slug(self) -> str:
    #    return f"refuges-{self.source.get_id()}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(fr=self._props.nom, de=self._props.nom)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_name(self) -> str:
        return "refuges"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> TranslationSchema:
        # return TranslationSchema(fr=self._props.description.valeur or "")
        return TranslationSchema(fr=self._props.remarque.valeur or "")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def author(self) -> AuthorSchema | None:
        if self.description.fr:
            return AuthorSchema(name="Les refuges.info contributors", url="https://www.refuges.info")
        else:
            return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> SourceSchema | None:
        return SourceSchema(
            name=self.source_name,
            ident=self.source_data.get_id(),
            url=self._props.lien,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def license(self) -> LicenseSchema | None:  # noqa: A003
        return refuges_lic

    @computed_field  # type: ignore[prop-decorator]
    @property
    def notes(self) -> list[TranslationSchema]:
        _note_fr = self._props.remarque.valeur or ""
        _note_de = ""
        if self._props.etat == "cle_a_recuperer":
            _note_fr = f"Clés nécessaires \n\n{_note_fr}".strip()
            _note_de = "Schlüssel erforderlich"
        if _note_fr:
            return [TranslationSchema(fr=_note_fr, de=_note_de)]
        return []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def owner(self) -> OwnerSchema | None:
        return None

    @computed_field()  # type: ignore[prop-decorator]
    @property
    def photos(self) -> list[PhotoSchema]:
        if self.include_photos is False:
            return []
        return get_original_images(self.source_data.get_id())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return self._props.info_comp.site_officiel.url or ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capacity(self) -> CapacitySchema:
        try:
            return CapacitySchema(open=int(self._props.places.valeur), closed=None)  # type: ignore  # noqa: PGH003
        except TypeError:
            return CapacitySchema(open=None, closed=None)

    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def hut_type(self) -> HutTypeSchema:
        return guess_hut_type(
            name=self.name.i18n or "",
            default=WODORE_HUT_TYPES.get(self._props.hut_type.ident, HutTypeEnum.unknown),
            capacity=self.capacity,
            elevation=self.location.ele,
            operator=None,
            missing_walls=self._props.info_comp.manque_un_mur.valeur or "0",
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_public(self) -> bool:
        return self._props.etat.ident in ["ouverture", "cle_a_recuperer"] or self._props.etat.ident is None
