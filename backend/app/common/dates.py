from datetime import datetime, timezone


def now_utc() -> datetime:
    """Date et heure courantes en UTC avec fuseau horaire."""
    return datetime.now(timezone.utc)


def to_naive_utc(dt: datetime) -> datetime:
    """Normalise une date en UTC sans fuseau (compatibilite colonnes SQL sans fuseau)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def utc_iso(dt: datetime) -> str:
    """Chaine ISO normalisee en UTC tronquee a la seconde pour empreinte deterministe."""
    return to_naive_utc(dt).replace(microsecond=0).isoformat()


def format_display_datetime(dt: datetime) -> str:
    """Formatage d'affichage lisible de date/heure en UTC."""
    dt_utc = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(timezone.utc).strftime("%d/%m/%Y a %H:%M (GMT)")
