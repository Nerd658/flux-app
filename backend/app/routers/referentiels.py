from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import csrf_protect, get_current_user
from app.models import Direction, FluxType, User
from app.schemas import DirectionIn, DirectionOut, FluxTypeIn, LabelOut, ReferentielsOut
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
        extra["manager_cuid"] = data.manager_cuid.strip().upper()
    return ReferentialService.add_label(db, Direction, data.libelle, user, request, "DIRECTION_CREATED", **extra)
