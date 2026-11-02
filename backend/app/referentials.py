"""Module de transition pour retro-compatibilite des referentiels."""
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import Country, Direction, FluxType, User, Zone
from app.services.referential_service import (
    MAX_ITEMS_PER_LIST,
    REFERENTIAL_REGISTRY,
    ReferentialService,
)

KINDS = {k: (v.model, v.label) for k, v in REFERENTIAL_REGISTRY.items()}
MAX_ITEMS = MAX_ITEMS_PER_LIST


def exists_label(db: Session, model: Any, libelle: str, exclude_id: int | None = None) -> bool:
    return ReferentialService.exists_label(db, model, libelle, exclude_id)


def add_label(db: Session, model: Any, libelle: str, user: User, request: Request, action: str):
    return ReferentialService.add_label(db, model, libelle, user, request, action)
