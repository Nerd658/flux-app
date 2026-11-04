"""Création des tables et des données initiales (idempotent : relançable sans doublon)."""
import secrets

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine, migrate_schema
from app.models import Country, Departement, Direction, FluxType, Role, StatutProfessionnel, User, Zone

FLUX_TYPES = ["HA", "Internet"]
DIRECTIONS = ["CX", "RSSI"]
ZONES = [f"Zone{i}" for i in range(1, 6)]           # remplacées plus tard par les vraies zones
COUNTRIES = ["Burkina Faso"]

# Comptes fictifs (en attendant l'AD)
# (CUID, email, nom, prénom, téléphone, direction, département, rôle)
FAKE_USERS = [
    ("DEMD0001", "awa.ouedraogo@fluxapp.bf", "Ouedraogo", "Awa", "+22670000001", "CX", "Service Client", Role.demandeur),
    ("MGR00001", "moussa.traore@fluxapp.bf", "Traore", "Moussa", "+22670000005", "CX", "Service Client", Role.manager),
    ("SECU0001", "fatou.bamba@fluxapp.bf", "Bamba", "Fatou", "+22670000006", "RSSI", "Securite Operationnelle", Role.securite),
    ("RSSI0001", "ibrahim.kone@fluxapp.bf", "Kone", "Ibrahim", "+22670000007", "RSSI", "Securite Operationnelle", Role.rssi),
    ("ADMN0001", "admin@fluxapp.bf", "Admin", "Système", "+22670000004", "RSSI", "Gouvernance SI", Role.admin),
]


def _seed_labels(db: Session, model, labels: list[str]) -> None:
    """Insère chaque libellé s'il n'existe pas déjà."""
    existing = set(db.scalars(select(model.libelle)))
    db.add_all(model(libelle=l) for l in labels if l not in existing)


def _seed_directions(db: Session) -> None:
    tree = [
        ("CX", "MGR00001", [("Service Client", "MGR00001"), ("Qualite & Process", "MGR00001")]),
        ("RSSI", "RSSI0001", [("Securite Operationnelle", "RSSI0001"), ("Gouvernance SI", "RSSI0001")]),
    ]
    for dir_lib, dir_mgr, depts in tree:
        d = db.scalar(select(Direction).where(Direction.libelle == dir_lib))
        if not d:
            d = Direction(libelle=dir_lib, manager_cuid=dir_mgr)
            db.add(d)
            db.flush()
        elif not d.manager_cuid:
            d.manager_cuid = dir_mgr
            db.flush()

        for dept_lib, dept_mgr in depts:
            dept = db.scalar(
                select(Departement).where(
                    Departement.direction_id == d.id,
                    Departement.libelle == dept_lib,
                )
            )
            if not dept:
                db.add(Departement(direction_id=d.id, libelle=dept_lib, manager_cuid=dept_mgr))
            elif not dept.manager_cuid:
                dept.manager_cuid = dept_mgr


def _seed_users(db: Session) -> None:
    settings = get_settings()
    # Pas de mot de passe par défaut connu : sinon on en génère un aléatoire, affiché une seule fois
    password = settings.seed_password or secrets.token_urlsafe(16)
    ph = PasswordHasher()
    created = False
    for cuid, email, nom, prenom, tel, direction, dept, role in FAKE_USERS:
        existing = db.scalar(select(User).where(User.cuid == cuid))
        if existing:
            if settings.seed_password:
                existing.password_hash = ph.hash(settings.seed_password)
            if not existing.direction:
                existing.direction = direction
            if existing.departement in ("CX", "RSSI", "Non renseignee", None):
                existing.departement = dept
            continue
        db.add(User(cuid=cuid, email=email, nom=nom, prenom=prenom, telephone=tel,
                    direction=direction, departement=dept, role=role, statut_pro=StatutProfessionnel.employe,
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
