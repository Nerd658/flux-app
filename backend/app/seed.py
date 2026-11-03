"""Création des tables et des données initiales (idempotent : relançable sans doublon)."""
import secrets

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine, migrate_schema
from app.models import Country, Direction, FluxType, Role, StatutProfessionnel, User, Zone

FLUX_TYPES = ["HA", "Internet"]
DIRECTIONS = ["CX", "RSSI"]
ZONES = [f"Zone{i}" for i in range(1, 6)]           # remplacées plus tard par les vraies zones
COUNTRIES = ["Burkina Faso"]

# Comptes fictifs (en attendant l'AD)
# (CUID, email, nom, prénom, téléphone, département, rôle)
FAKE_USERS = [
    ("DEMD0001", "awa.ouedraogo@fluxapp.bf", "Ouedraogo", "Awa", "+22670000001", "CX", Role.demandeur),
    ("MGR00001", "moussa.traore@fluxapp.bf", "Traore", "Moussa", "+22670000005", "CX", Role.manager),
    ("SECU0001", "fatou.bamba@fluxapp.bf", "Bamba", "Fatou", "+22670000006", "RSSI", Role.securite),
    ("RSSI0001", "ibrahim.kone@fluxapp.bf", "Kone", "Ibrahim", "+22670000007", "RSSI", Role.rssi),
    ("ADMN0001", "admin@fluxapp.bf", "Admin", "Système", "+22670000004", "RSSI", Role.admin),
]


def _seed_labels(db: Session, model, labels: list[str]) -> None:
    """Insère chaque libellé s'il n'existe pas déjà."""
    existing = set(db.scalars(select(model.libelle)))
    db.add_all(model(libelle=l) for l in labels if l not in existing)


def _seed_directions(db: Session) -> None:
    directions = [("CX", "MGR00001"), ("RSSI", "RSSI0001")]
    for libelle, mgr_cuid in directions:
        d = db.scalar(select(Direction).where(Direction.libelle == libelle))
        if not d:
            db.add(Direction(libelle=libelle, manager_cuid=mgr_cuid))
        elif not d.manager_cuid:
            d.manager_cuid = mgr_cuid


def _seed_users(db: Session) -> None:
    settings = get_settings()
    # Pas de mot de passe par défaut connu : sinon on en génère un aléatoire, affiché une seule fois
    password = settings.seed_password or secrets.token_urlsafe(16)
    ph = PasswordHasher()
    created = False
    for cuid, email, nom, prenom, tel, dept, role in FAKE_USERS:
        if db.scalar(select(User).where(User.cuid == cuid)):
            continue
        db.add(User(cuid=cuid, email=email, nom=nom, prenom=prenom, telephone=tel,
                    departement=dept, role=role, statut_pro=StatutProfessionnel.employe,
                    password_hash=ph.hash(password)))
        created = True
    if created and not settings.seed_password:
        print(f"[seed] Mot de passe des comptes fictifs : {password}")


def run() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)
    with SessionLocal() as db, db.begin():   # transaction unique : tout ou rien
        _seed_labels(db, FluxType, FLUX_TYPES)
        _seed_directions(db)
        _seed_labels(db, Zone, ZONES)
        _seed_labels(db, Country, COUNTRIES)
        _seed_users(db)


if __name__ == "__main__":
    run()
