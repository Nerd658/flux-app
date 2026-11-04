from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import csrf_protect, require_roles
from app.models import Role, User
from app.schemas import (
    AuditOut,
    LabelIn,
    LabelUsageOut,
    RoleAssignOut,
    StatsOut,
    UserAdminOut,
    UserCreateIn,
    UserRoleIn,
    UserStatusIn,
)
from app.services.admin_service import AdminService
from app.services.referential_service import ReferentialService

admin_only = require_roles(Role.admin)
router = APIRouter(prefix="/api/admin", tags=["administration"], dependencies=[Depends(admin_only)])
csrf = [Depends(csrf_protect)]


# ---------- Tableau de bord ----------

@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    return AdminService.get_stats(db)


# ---------- Comptes ----------

@router.get("/users", response_model=list[UserAdminOut])
def list_users(db: Session = Depends(get_db)):
    return AdminService.list_users(db)


@router.post("/users", response_model=RoleAssignOut, dependencies=csrf)
def assign_by_cuid(
    data: UserCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    return AdminService.create_or_assign_by_cuid(db, data, admin, request)


@router.put("/users/{user_id}", response_model=RoleAssignOut, dependencies=csrf)
def update_role(
    user_id: int,
    data: UserRoleIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    return AdminService.update_role(db, user_id, data, admin, request)


@router.post("/users/{user_id}/status", response_model=UserAdminOut, dependencies=csrf)
def set_user_status(
    user_id: int,
    data: UserStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    return AdminService.set_user_status(db, user_id, data, admin, request)


# ---------- Referentiels ----------

@router.get("/referentiels", response_model=dict[str, list[LabelUsageOut]])
def list_referentials(db: Session = Depends(get_db)):
    return ReferentialService.list_with_usage(db)


@router.post(
    "/referentiels/{kind}",
    response_model=LabelUsageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=csrf,
)
def create_referential(
    kind: str,
    data: LabelIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    return ReferentialService.create_referential(
        db,
        kind,
        data.libelle,
        admin,
        request,
        manager_cuid=data.manager_cuid,
        direction_id=data.direction_id,
        direction_libelle=data.direction_libelle,
    )


@router.put("/referentiels/{kind}/{item_id}", response_model=LabelUsageOut, dependencies=csrf)
def rename_referential(
    kind: str,
    item_id: int,
    data: LabelIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    return ReferentialService.rename_referential(
        db,
        kind,
        item_id,
        data.libelle,
        admin,
        request,
        manager_cuid=data.manager_cuid,
        direction_id=data.direction_id,
    )


@router.delete("/referentiels/{kind}/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=csrf)
def delete_referential(
    kind: str,
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    ReferentialService.delete_referential(db, kind, item_id, admin, request)


# ---------- Journal d'audit ----------

@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    db: Session = Depends(get_db),
    categorie: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=50),
    before_id: int | None = Query(None, gt=0),
    limit: int = Query(50, ge=1, le=100),
):
    return AdminService.list_audit_logs(db, categorie, q, before_id, limit)
