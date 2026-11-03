import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Énumérations ----------

class Role(str, enum.Enum):
    demandeur = "demandeur"
    manager = "manager"
    securite = "securite"
    rssi = "rssi"
    admin = "admin"
    validateur_n1 = "validateur_n1"
    validateur_final = "validateur_final"


class Periode(str, enum.Enum):
    temporaire = "temporaire"
    permanente = "permanente"


class Statut(str, enum.Enum):
    soumise = "soumise"                        # Niveau 1 : en attente du manager de departement
    validee_manager = "validee_manager"        # Niveau 2 : en attente du validateur technique (securite)
    validee_technique = "validee_technique"    # Niveau 3 : en attente du RSSI
    validee = "validee"                        # Validee definitivement -> PDF disponible
    refusee = "refusee"                        # Refusee avec motif obligatoire
    validee_n1 = "validee_n1"
    refusee_n1 = "refusee_n1"


class Decision(str, enum.Enum):
    validee = "validee"
    refusee = "refusee"


class StatutProfessionnel(str, enum.Enum):
    employe = "employe"
    prestataire = "prestataire"
    stagiaire = "stagiaire"


# ---------- Utilisateurs (authentification fictive avant AD) ----------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuid: Mapped[str] = mapped_column(String(32), unique=True, index=True)   # identifiant de connexion
    email: Mapped[str] = mapped_column(String(255), unique=True)          # affiché sur la demande
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    telephone: Mapped[str] = mapped_column(String(30))
    departement: Mapped[str] = mapped_column(String(150))
    statut_pro: Mapped[StatutProfessionnel | None] = mapped_column(Enum(StatutProfessionnel), nullable=True, default=None)
    password_hash: Mapped[str] = mapped_column(String(255))          # Argon2id, jamais en clair
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.demandeur)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Clés du sceau cryptographique (validateurs uniquement)
    public_key: Mapped[str | None] = mapped_column(Text)             # PEM Ed25519
    private_key_enc: Mapped[str | None] = mapped_column(Text)        # PEM chiffré par clé maître
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def display_name(self) -> str:
        return f"{self.prenom} {self.nom.upper()}"


# ---------- Référentiels (listes déroulantes) ----------

class FluxType(Base):
    """Type d'ouverture de flux (HA, Internet, ...) ; extensible par les utilisateurs."""
    __tablename__ = "flux_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(80), unique=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Direction(Base):
    """Direction du demandeur (CX, RSSI, ...) ; extensible par les utilisateurs."""
    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(150), unique=True)
    manager_cuid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def authorized_managers(self) -> list[str]:
        if not self.manager_cuid:
            return []
        return [c.strip().upper() for c in self.manager_cuid.replace(";", ",").split(",") if c.strip()]


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(80), unique=True)


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(80), unique=True)


# ---------- Demande et lignes de flux ----------

class FluxRequest(Base):
    __tablename__ = "flux_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # ex. DOF-2026-000001
    flux_type_id: Mapped[int] = mapped_column(ForeignKey("flux_types.id"))
    flux_type_label: Mapped[str] = mapped_column(String(80))       # libellé figé (sceau stable)
    demandeur_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Instantané du demandeur au moment de la soumission (le document reste figé)
    dem_nom: Mapped[str] = mapped_column(String(100))
    dem_prenom: Mapped[str] = mapped_column(String(100))
    dem_email: Mapped[str] = mapped_column(String(255))
    dem_telephone: Mapped[str] = mapped_column(String(30))
    dem_statut_pro: Mapped[StatutProfessionnel] = mapped_column(
        Enum(StatutProfessionnel), default=StatutProfessionnel.employe
    )
    departement: Mapped[str] = mapped_column(String(150))

    # Manager rattache au departement ou saisi librement
    manager_cuid: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    mgr_nom: Mapped[str] = mapped_column(String(100))
    mgr_prenom: Mapped[str] = mapped_column(String(100))
    mgr_email: Mapped[str] = mapped_column(String(255))
    mgr_telephone: Mapped[str] = mapped_column(String(30))

    periode: Mapped[Periode] = mapped_column(Enum(Periode))
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)          # obligatoire si temporaire

    statut: Mapped[Statut] = mapped_column(Enum(Statut), default=Statut.soumise, index=True)
    ticket_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64))         # SHA-256 du contenu canonique
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    flux_type: Mapped[FluxType] = relationship()
    demandeur: Mapped[User] = relationship()
    lines: Mapped[list["FluxLine"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="FluxLine.numero"
    )
    validations: Mapped[list["Validation"]] = relationship(
        back_populates="request", order_by="Validation.niveau"
    )


class FluxLine(Base):
    __tablename__ = "flux_lines"
    __table_args__ = (UniqueConstraint("request_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("flux_requests.id", ondelete="CASCADE"))
    numero: Mapped[int] = mapped_column(Integer)

    # Les libellés des référentiels sont figés à la soumission (validés contre les listes
    # du moment) : renommer une zone plus tard n'altère ni le document ni son sceau.

    # Source
    src_ip: Mapped[str] = mapped_column(String(255))              # IP / CIDR, séparés par virgules
    src_zone: Mapped[str] = mapped_column(String(80))
    src_pays: Mapped[str] = mapped_column(String(80))
    src_app: Mapped[str] = mapped_column(String(255))

    # Destination
    dst_ip: Mapped[str] = mapped_column(String(255))
    dst_ports: Mapped[str] = mapped_column(String(255))           # ex. "443,8080-8090" ; vide si ICMP
    protocole: Mapped[str] = mapped_column(String(10))            # TCP / UDP / ICMP
    dst_zone: Mapped[str] = mapped_column(String(80))
    dst_pays: Mapped[str] = mapped_column(String(80))
    dst_app: Mapped[str] = mapped_column(String(255))

    type_acces: Mapped[str] = mapped_column(String(80))           # « zone source - zone destination », calculé
    justification: Mapped[str] = mapped_column(Text)

    request: Mapped[FluxRequest] = relationship(back_populates="lines")


# ---------- Validations signées ----------

class Validation(Base):
    __tablename__ = "validations"
    __table_args__ = (UniqueConstraint("request_id", "niveau"),)  # une décision par niveau

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("flux_requests.id"))
    niveau: Mapped[int] = mapped_column(Integer)                  # 1 = N1, 2 = final
    validateur_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[Decision] = mapped_column(Enum(Decision))
    commentaire: Mapped[str | None] = mapped_column(Text)         # obligatoire si refus
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    signed_hash: Mapped[str] = mapped_column(String(64))          # hash signé (contenu + décision)
    signature: Mapped[str] = mapped_column(Text)                  # Ed25519, base64
    key_fingerprint: Mapped[str] = mapped_column(String(64))      # SHA-256 de la clé publique

    request: Mapped[FluxRequest] = relationship(back_populates="validations")
    validateur: Mapped[User] = relationship()


# ---------- Historique des clés publiques de signature ----------

class SigningKey(Base):
    """Clé publique de chaque validateur, conservée même après renouvellement (vérification des anciennes signatures)."""
    __tablename__ = "signing_keys"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)   # SHA-256 de la clé publique brute
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    public_key: Mapped[str] = mapped_column(Text)                             # PEM Ed25519
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------- Journal d'audit (append-only) ----------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60), index=True)   # ex. LOGIN_FAILED, REQUEST_SUBMITTED
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[str | None] = mapped_column(Text)             # jamais de mot de passe / token
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
