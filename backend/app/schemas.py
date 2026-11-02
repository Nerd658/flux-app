"""Schémas Pydantic : validation stricte des entrées, exposition minimale des sorties."""
import ipaddress
import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator

from app.models import Decision, Periode, Role, Statut


class StrictModel(BaseModel):
    # Champs inconnus refusés (anti mass-assignment), espaces superflus supprimés
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- Authentification ----------

class LoginIn(StrictModel):
    # CUID : alphanumérique uniquement (liste blanche), normalisé en majuscules
    cuid: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9]+$")
    password: str = Field(min_length=1, max_length=128)   # mot de passe applicatif ; borne haute anti-DoS Argon2


class ProfileUpdateIn(StrictModel):
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    email: EmailStr
    telephone: str = Field(default="", max_length=30)
    departement: str = Field(default="", max_length=150)


class UserOut(BaseModel):
    # Minimisation : ni hash, ni clés, ni dates internes
    model_config = ConfigDict(from_attributes=True)

    id: int
    cuid: str
    email: str
    nom: str
    prenom: str
    telephone: str
    departement: str
    role: Role

    @computed_field
    @property
    def profil_incomplet(self) -> bool:
        return (
            self.prenom in ("-", "", None)
            or self.nom == self.cuid
            or self.email.endswith("@annuaire.invalid")
        )


# ---------- Référentiels ----------

class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    libelle: str


class DirectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    libelle: str
    manager_cuid: str | None = None


class ReferentielsOut(BaseModel):
    flux_types: list[LabelOut]
    directions: list[DirectionOut]
    zones: list[LabelOut]
    pays: list[LabelOut]


class FluxTypeIn(StrictModel):
    # Liste blanche de caractères : lettres, chiffres, espace, . - / ( ) _
    libelle: str = Field(min_length=2, max_length=40, pattern=r"^[\w .\-/()]+$")


class DirectionIn(StrictModel):
    libelle: str = Field(min_length=2, max_length=150, pattern=r"^[\w .\-/()]+$")
    manager_cuid: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9]*$")


# ---------- Demande ----------

_NAME = r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$"           # lettres unicode, espaces, tirets, apostrophes
_PHONE = r"^\+?[0-9 ]{8,20}$"
_FREE_TEXT = r"^[^\x00-\x1f\x7f]*$"                   # pas de caractères de contrôle


def _validate_ip_list(v: str) -> str:
    """Une ou plusieurs IP / CIDR (IPv4 ou IPv6) séparées par des virgules ; renvoie la forme normalisée."""
    items = [x.strip() for x in v.split(",") if x.strip()]
    if not 1 <= len(items) <= 20:
        raise ValueError("1 à 20 adresses IP attendues")
    out = []
    for item in items:
        try:
            net = ipaddress.ip_network(item, strict=False)
        except ValueError:
            raise ValueError(f"adresse IP invalide : {item[:50]}") from None
        out.append(str(net.network_address) if net.num_addresses == 1 else str(net))
    return ", ".join(out)


def _validate_ports(v: str) -> str:
    """Format accepté : 443 ou 8080-8090, séparés par des virgules ; bornes 1-65535."""
    items = [x.strip() for x in v.split(",") if x.strip()]
    if not 1 <= len(items) <= 30:
        raise ValueError("1 à 30 ports / plages attendus")
    for item in items:
        if not re.fullmatch(r"\d{1,5}(-\d{1,5})?", item):
            raise ValueError(f"port invalide : {item[:20]}")
        bounds = [int(p) for p in item.split("-")]
        if not all(1 <= p <= 65535 for p in bounds) or bounds != sorted(bounds):
            raise ValueError(f"plage de ports invalide : {item}")
    return ",".join(items)


ACCESS_TYPE_MAX = 80


def access_type(src_zone: str, dst_zone: str) -> str:
    """Type d'accès d'un flux : combinaison zone source - zone destination (ex. « Prod - Préprod »)."""
    return f"{src_zone} - {dst_zone}"


class Personne(StrictModel):
    nom: str = Field(min_length=1, max_length=100, pattern=_NAME)
    prenom: str = Field(min_length=1, max_length=100, pattern=_NAME)
    email: EmailStr
    telephone: str = Field(pattern=_PHONE)


class FluxLineIn(StrictModel):
    src_ip: str = Field(min_length=2, max_length=500)
    src_zone: str = Field(min_length=1, max_length=80)
    src_pays: str = Field(min_length=1, max_length=80)
    src_app: str = Field(min_length=1, max_length=255, pattern=_FREE_TEXT)
    dst_ip: str = Field(min_length=2, max_length=500)
    dst_ports: str = Field(default="", max_length=255)
    # Saisie libre mais liste blanche de caractères (ex. TCP, UDP, ICMP, TCP/UDP, GRE) ; 10 car. max (colonne en base)
    protocole: str = Field(min_length=2, max_length=10, pattern=r"^[A-Za-z0-9/_-]+$")
    dst_zone: str = Field(min_length=1, max_length=80)
    dst_pays: str = Field(min_length=1, max_length=80)
    dst_app: str = Field(min_length=1, max_length=255, pattern=_FREE_TEXT)
    justification: str = Field(min_length=5, max_length=2000)

    # Type d'accès = « zone source - zone destination » : calculé ici, jamais saisi ni envoyé par le client
    @computed_field
    @property
    def type_acces(self) -> str:
        return access_type(self.src_zone, self.dst_zone)

    @field_validator("src_ip", "dst_ip")
    @classmethod
    def check_ips(cls, v: str) -> str:
        return _validate_ip_list(v)

    @model_validator(mode="after")
    def check_proto_ports(self):
        self.protocole = self.protocole.upper()          # forme canonique (scellée telle quelle)
        if self.protocole == "ICMP":
            self.dst_ports = ""                          # ICMP n'utilise pas de ports
        elif not self.dst_ports.strip():
            raise ValueError("port(s) obligatoire(s)")
        else:
            self.dst_ports = _validate_ports(self.dst_ports)
        if len(self.type_acces) > ACCESS_TYPE_MAX:      # colonne type_acces : 80 caractères
            raise ValueError("noms de zones trop longs pour former le type d'accès")
        return self


class FluxRequestIn(StrictModel):
    flux_type_id: int = Field(gt=0)
    manager: Personne
    departement: str = Field(min_length=1, max_length=150, pattern=_FREE_TEXT)
    manager_cuid: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9]*$")
    periode: Periode
    date_debut: date
    date_fin: date | None = None
    lines: list[FluxLineIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def check_dates(self):
        if self.date_debut < date.today():
            raise ValueError("la date de début ne peut pas être passée")
        if self.periode == Periode.temporaire:
            if not self.date_fin:
                raise ValueError("date de fin obligatoire pour une ouverture temporaire")
            if self.date_fin < self.date_debut:
                raise ValueError("la date de fin doit suivre la date de début")
        else:
            self.date_fin = None          # une ouverture permanente n'a pas de fin
        return self


class DecisionIn(StrictModel):
    decision: Decision
    commentaire: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def comment_if_refused(self):
        # Un refus doit toujours être justifié
        if self.decision == Decision.refusee and not (self.commentaire and len(self.commentaire) >= 5):
            raise ValueError("un commentaire d'au moins 5 caractères est obligatoire en cas de refus")
        return self


# ---------- Sorties ----------

class PersonneOut(BaseModel):
    nom: str
    prenom: str
    email: str
    telephone: str


class FluxLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    numero: int
    src_ip: str
    src_zone: str
    src_pays: str
    src_app: str
    dst_ip: str
    dst_ports: str
    protocole: str
    dst_zone: str
    dst_pays: str
    dst_app: str
    type_acces: str
    justification: str


class ValidationOut(BaseModel):
    niveau: int
    validateur: str            # « Prénom NOM » uniquement (minimisation)
    decision: Decision
    commentaire: str | None
    decided_at: datetime
    key_fingerprint: str


class RequestSummary(BaseModel):
    id: int
    reference: str
    flux_type: str
    demandeur: str
    statut: Statut
    created_at: datetime
    nb_lignes: int


class RequestDetail(BaseModel):
    id: int | None = None                # absent en prévisualisation
    reference: str | None = None
    statut: Statut | None = None
    created_at: datetime | None = None
    content_hash: str | None = None
    flux_type: str
    demandeur: PersonneOut
    manager: PersonneOut
    manager_cuid: str | None = None
    departement: str
    periode: Periode
    date_debut: date
    date_fin: date | None
    lines: list[FluxLineOut]
    validations: list[ValidationOut] = []


class ValidatorStatsOut(BaseModel):
    a_traiter: int
    en_retard: int          # en attente depuis plus de 48 h
    validees_mois: int      # décisions du validateur connecté depuis le 1er du mois (UTC)
    refusees_mois: int


class VerifyOut(BaseModel):
    reference: str
    contenu_intact: bool
    signatures: list[dict]
    document_fiable: bool


# ---------- Administration ----------

class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cuid: str
    nom: str
    prenom: str
    email: str
    telephone: str
    departement: str
    role: Role
    is_active: bool
    created_at: datetime

    # Compte enregistré par l'administrateur, identité pas encore reçue de l'annuaire
    @computed_field
    @property
    def en_attente(self) -> bool:
        return self.email.endswith(PENDING_EMAIL_DOMAIN)


PENDING_EMAIL_DOMAIN = "@attente.invalid"


class UserRoleIn(StrictModel):
    """L'administrateur n'attribue que des rôles : l'identité vient de l'annuaire."""
    role: Role


class UserCreateIn(UserRoleIn):
    cuid: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9]+$")

    @field_validator("role")
    @classmethod
    def not_requester(cls, v: Role) -> Role:
        if v == Role.demandeur:
            raise ValueError("inutile : tout CUID est demandeur par défaut")
        return v


class RoleAssignOut(BaseModel):
    user: UserAdminOut
    retires: list[str]      # CUID des anciens titulaires redevenus demandeurs


class UserStatusIn(StrictModel):
    is_active: bool


class LabelIn(StrictModel):
    """Libellé d'un référentiel (avec champ optionnel manager_cuid pour les directions)."""
    libelle: str = Field(min_length=2, max_length=150, pattern=r"^[\w .\-/()]+$")
    manager_cuid: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9]*$")


class LabelUsageOut(BaseModel):
    id: int
    libelle: str
    usage: int
    manager_cuid: str | None = None


class CountOut(BaseModel):
    label: str
    count: int


class StatsOut(BaseModel):
    total: int
    par_statut: dict[str, int]
    en_retard: int                     # en attente depuis plus de 48 h
    delai_moyen_heures: float | None   # soumission -> décision finale
    par_type: list[CountOut]
    utilisateurs_actifs: int
    recentes: list[RequestSummary]


class AuditOut(BaseModel):
    id: int
    created_at: datetime
    action: str
    acteur: str | None
    acteur_cuid: str | None
    entity: str | None
    entity_id: int | None
    ip: str | None
    details: str | None
