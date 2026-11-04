from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import csrf_protect, get_current_user
from app.models import Direction, FluxType, User
from app.schemas import (
    DepartementIn,
    DepartementOut,
    DirectionIn,
    DirectionOut,
    FluxTypeIn,
    LabelOut,
    ReferentielsOut,
)
from app.services.referential_service import ReferentialService

router = APIRouter(prefix="/api/referentiels", tags=["referentiels"])


@router.get("", response_model=ReferentielsOut)
def list_referentiels(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Toutes les listes deroulantes du formulaire en un seul appel."""
    return ReferentialService.list_all(db)


@router.post(
    "/flux-types",
    response_model=LabelOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(csrf_protect)],
)
def add_flux_type(
    data: FluxTypeIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ajout d'un type d'ouverture, partage ensuite avec tous les utilisateurs."""
    return ReferentialService.add_label(db, FluxType, data.libelle, user, request, "FLUX_TYPE_CREATED")


@router.post(
    "/directions",
    response_model=DirectionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(csrf_protect)],
)
def add_direction(
    data: DirectionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ajout d'une direction, partagee ensuite avec tous les utilisateurs."""
    extra = {}
    if data.manager_cuid:
        extra["manager_cuid"] = ReferentialService._normalize_manager_cuid(data.manager_cuid)
    item = ReferentialService.add_label(db, Direction, data.libelle, user, request, "DIRECTION_CREATED", **extra)
    mgr_map = ReferentialService._resolve_managers_map(db, [item])
    return DirectionOut(
        id=item.id,
        libelle=item.libelle,
        manager_cuid=item.manager_cuid,
        managers=mgr_map.get(item.id, []),
    )


@router.post(
    "/departements",
    response_model=DepartementOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(csrf_protect)],
)
def add_departement(
    data: DepartementIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ajout d'un departement lie a une direction, partage ensuite avec tous les utilisateurs."""
    out = ReferentialService.create_referential(
        db,
        "departements",
        data.libelle,
        user,
        request,
        manager_cuid=data.manager_cuid,
        direction_id=data.direction_id,
        direction_libelle=data.direction_libelle,
    )
    return DepartementOut(
        id=out.id,
        direction_id=out.direction_id or 0,
        direction_libelle=out.direction_libelle or "",
        libelle=out.libelle,
        manager_cuid=out.manager_cuid,
        managers=out.managers,
    )
