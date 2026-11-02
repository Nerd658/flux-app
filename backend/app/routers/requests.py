from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import csrf_protect, get_current_user, require_roles
from app.models import Role, User
from app.schemas import (
    DecisionIn,
    FluxRequestIn,
    RequestDetail,
    RequestSummary,
    ValidatorStatsOut,
    VerifyOut,
)
from app.services.request_service import RequestService, VALIDATORS

router = APIRouter(prefix="/api/requests", tags=["demandes"])

# Retro-compatibilite des imports internes
_summaries = RequestService.to_summaries
VALIDATOR_ROLES = (Role.manager, Role.securite, Role.rssi)


# ---------- Demandeur ----------

@router.post("/preview", response_model=RequestDetail, dependencies=[Depends(csrf_protect)])
def preview(
    data: FluxRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.demandeur)),
):
    """Recapitulatif valide cote serveur, sans enregistrement."""
    return RequestService.preview(db, data, user)


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED, dependencies=[Depends(csrf_protect)])
def submit(
    data: FluxRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.demandeur)),
):
    return RequestService.submit(db, data, user, request)


@router.get("/mine", response_model=list[RequestSummary])
def my_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return RequestService.list_mine(db, user)


# ---------- Validateurs ----------

@router.get("/pending", response_model=list[RequestSummary])
def pending(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VALIDATOR_ROLES)),
):
    """File d'attente du validateur : uniquement les demandes a son niveau."""
    return RequestService.list_pending(db, user)


@router.get("/validator-stats", response_model=ValidatorStatsOut)
def validator_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VALIDATOR_ROLES)),
):
    return RequestService.get_validator_stats(db, user)


@router.get("/all", response_model=list[RequestSummary])
def all_requests(db: Session = Depends(get_db), _: User = Depends(require_roles(*VALIDATORS))):
    return RequestService.list_all(db)


@router.post("/{request_id}/decision", response_model=RequestDetail, dependencies=[Depends(csrf_protect)])
def decide(
    request_id: int,
    data: DecisionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VALIDATOR_ROLES)),
):
    return RequestService.decide(db, request_id, data, user, request)


# ---------- Commun ----------

@router.get("/{request_id}", response_model=RequestDetail)
def get_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = RequestService.load(db, request_id)
    RequestService.check_access(user, req)
    return RequestService.to_detail(req)


@router.get("/{request_id}/verify", response_model=VerifyOut)
def verify(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return RequestService.verify(db, request_id, user)


@router.get("/{request_id}/pdf")
def download_pdf(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return RequestService.download_pdf(db, request_id, user, request)
