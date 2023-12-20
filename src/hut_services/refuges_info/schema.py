import logging
from enum import Enum
from typing import Literal

from geojson_pydantic import Feature, FeatureCollection, Point
from pydantic import BaseModel, Field, computed_field

from hut_services.core.schema import (
    BaseHutConverterSchema,
    BaseHutSourceSchema,
    CapacitySchema,
    HutTypeEnum,
    OwnerSchema,
    SourcePropertiesSchema,
)
from hut_services.core.schema.geo import LocationSchema
from hut_services.core.schema.locale import TranslationSchema

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
    7: HutTypeEnum.unattended_hut,
    10: HutTypeEnum.hut,
    9: HutTypeEnum.hut,
    28: HutTypeEnum.basic_hotel,
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
    ident: Literal["ouverture", "fermeture", "cle_a_recuperer", "detruit"] | None = Field(..., alias="id")  # type: ignore[assignment]


class _Date(BaseModel):
    derniere_modif: str
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


class RefugesInfoFeature(Feature):
    """RefugesInfo Feature Model with required properties and geometry."""

    geometry: Point
    properties: _RefugesInfoFeatureProperties

    def get_id(self) -> str:
        return str(self.properties.ident)

    def get_name(self) -> str:
        return str(self.properties.nom)

    def get_location(self) -> LocationSchema:
        # coords = self.geometry.coordinates
        return LocationSchema(
            lat=self.properties.coord.lat, lon=self.properties.coord.long, ele=self.properties.coord.alt
        )

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

    source_name: str = "refuges_info"


class RefugesInfoHut0Convert(BaseHutConverterSchema[RefugesInfoFeature]):
    @property
    def _props(self) -> _RefugesInfoFeatureProperties:
        return self.source.properties

    @computed_field  # type: ignore[misc]
    @property
    def slug(self) -> str:
        return f"refuges-{self.source.get_id()}"

    @computed_field  # type: ignore[misc]
    @property
    def name(self) -> TranslationSchema:
        return TranslationSchema(fr=self._props.nom, de=self._props.nom)

    @computed_field  # type: ignore[misc]
    @property
    def description(self) -> TranslationSchema:
        return TranslationSchema(fr=self._props.description.valeur or "")

    @computed_field  # type: ignore[misc]
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

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        return self._props.info_comp.site_officiel.url or ""

    @computed_field  # type: ignore[misc]
    @property
    def capacity(self) -> CapacitySchema:
        try:
            return CapacitySchema(opened=int(self._props.places.valeur))  # type: ignore  # noqa: PGH003
        except TypeError:
            return CapacitySchema(opened=None, closed=None)

    @computed_field(alias="type")  # type: ignore[misc]
    @property
    def hut_type(self) -> str:
        _type = WODORE_HUT_TYPES.get(self._props.hut_type.ident, "unknown")
        if _type == "unattended-hut":
            if self._props.info_comp.manque_un_mur.valeur or "0" != "0":
                _type = "basic-shelter"
            elif self.location.ele or 0 > 2500:
                _type = "bivouac"
        return _type

    @computed_field  # type: ignore[misc]
    @property
    def owner(self) -> OwnerSchema | None:
        name = self._props.proprio.valeur or ""
        comment = ""
        if name:
            comment = f"Full name: {name}"
            name = name[:100]
        if name:
            return OwnerSchema(name=name, comment=comment)
        return None

    @computed_field  # type: ignore[misc]
    @property
    def is_public(self) -> bool:
        return self._props.etat.ident in ["ouverture", "cle_a_recuperer"] or self._props.etat.ident is None
