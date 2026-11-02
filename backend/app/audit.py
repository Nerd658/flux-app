"""Journal d'audit : traçabilité des actions sensibles (jamais de secret dans `details`)."""
import ipaddress
import json
import logging

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditLog

logger = logging.getLogger("audit")


def client_ip(request: Request | None) -> str | None:
    """IP du poste. Derrière un reverse proxy de confiance, l'IP transmise par celui-ci (X-Forwarded-For) ;
    l'en-tête est ignoré s'il vient d'ailleurs (il serait falsifiable par le client)."""
    if not request or not request.client:
        return None
    peer = request.client.host
    if peer in get_settings().trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer


def client_agent(request: Request | None) -> str:
    """Navigateur et système du poste (tronqué) : complète l'IP dans le journal des connexions."""
    return (request.headers.get("user-agent", "") if request else "")[:200]


def audit(db: Session, action: str, *, actor_id: int | None = None, entity: str | None = None,
          entity_id: int | None = None, request: Request | None = None,
          details: dict | None = None, commit: bool = True) -> None:
    entry = AuditLog(
        actor_id=actor_id, action=action, entity=entity, entity_id=entity_id,
        ip=client_ip(request),
        details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
    )
    db.add(entry)
    if commit:
        db.commit()
    logger.info("%s actor=%s %s#%s", action, actor_id, entity, entity_id)
