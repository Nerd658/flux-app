from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # évite les connexions mortes (timeout MySQL)
    pool_recycle=3600,
    echo=False,              # ne jamais logguer les requêtes SQL (fuite de données)
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI : une session par requête, toujours refermée."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema(target_engine=None) -> None:
    """Ajoute les colonnes manquantes de façon idempotente (compatibilité sans perte de données)."""
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            dialect = eng.dialect.name
            if dialect == "sqlite":
                user_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)")}
                if user_cols and "statut_pro" not in user_cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN statut_pro VARCHAR(20) NULL")
                req_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(flux_requests)")}
                if req_cols and "dem_statut_pro" not in req_cols:
                    conn.exec_driver_sql("ALTER TABLE flux_requests ADD COLUMN dem_statut_pro VARCHAR(20) DEFAULT 'employe'")
            else:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN IF NOT EXISTS statut_pro VARCHAR(20) NULL")
                conn.exec_driver_sql("ALTER TABLE flux_requests ADD COLUMN IF NOT EXISTS dem_statut_pro VARCHAR(20) DEFAULT 'employe'")
            conn.commit()
    except Exception:
        pass
