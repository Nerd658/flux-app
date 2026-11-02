from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.common.dates import to_naive_utc
from app.models import AuditLog, FluxRequest, Role, Statut, User, Validation
from app.schemas import (
    PENDING_EMAIL_DOMAIN,
    AuditOut,
    CountOut,
    RoleAssignOut,
    StatsOut,
    UserAdminOut,
    UserCreateIn,
    UserRoleIn,
    UserStatusIn,
)
from app.services.auth_service import NO_LOCAL_PASSWORD
from app.services.request_service import RequestService

SINGLE_HOLDER: set[Role] = set()

CATEGORIES = {
    "connexions": ("LOGIN_", "LOGOUT"),
    "demandes": ("REQUEST_SUBMITTED", "PDF_", "SEAL_"),
    "decisions": ("REQUEST_VALIDEE", "REQUEST_REFUSEE", "SIGNING_KEY"),
    "administration": ("USER_", "REFERENTIAL_", "FLUX_TYPE_", "DIRECTION_"),
}


class AdminService:
    @staticmethod
    def get_stats(db: Session) -> StatsOut:
        counts = dict(db.execute(select(FluxRequest.statut, func.count()).group_by(FluxRequest.statut)).all())
        par_statut = {s.value: counts.get(s, 0) for s in Statut}

        limite = to_naive_utc(datetime.now(timezone.utc)) - timedelta(hours=48)
        en_retard = db.scalar(
            select(func.count())
            .select_from(FluxRequest)
            .where(
                FluxRequest.statut.in_([Statut.soumise, Statut.validee_manager, Statut.validee_technique]),
                FluxRequest.created_at < limite,
            )
        )

        rows = db.execute(
            select(FluxRequest.created_at, func.max(Validation.decided_at))
            .join(Validation, Validation.request_id == FluxRequest.id)
            .where(FluxRequest.statut.in_([Statut.validee, Statut.refusee]))
            .group_by(FluxRequest.id, FluxRequest.created_at)
        ).all()
        heures = [
            (to_naive_utc(fin) - to_naive_utc(debut)).total_seconds() / 3600
            for debut, fin in rows
            if debut and fin
        ]

        par_type = db.execute(
            select(FluxRequest.flux_type_label, func.count())
            .group_by(FluxRequest.flux_type_label)
            .order_by(func.count().desc())
        ).all()

        recentes = db.scalars(
            select(FluxRequest)
            .options(selectinload(FluxRequest.lines))
            .order_by(FluxRequest.created_at.desc())
            .limit(6)
        ).all()

        return StatsOut(
            total=sum(par_statut.values()),
            par_statut=par_statut,
            en_retard=en_retard,
            delai_moyen_heures=round(sum(heures) / len(heures), 1) if heures else None,
            par_type=[CountOut(label=label, count=n) for label, n in par_type],
            utilisateurs_actifs=db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))),
            recentes=RequestService.to_summaries(recentes),
        )

    @staticmethod
    def get_user(db: Session, user_id: int) -> User:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
        return user

    @staticmethod
    def other_active_admins(db: Session, user_id: int) -> int:
        return db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.admin, User.is_active.is_(True), User.id != user_id)
        )

    @classmethod
    def list_users(cls, db: Session) -> list[User]:
        return list(db.scalars(select(User).order_by(User.nom, User.prenom)))

    @classmethod
    def assign_role(cls, db: Session, user: User, role: Role, admin: User, request: Request) -> list[str]:
        if user.id == admin.id and role != user.role:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas modifier votre propre role")
        if (
            user.role == Role.admin
            and role != Role.admin
            and user.is_active
            and cls.other_active_admins(db, user.id) == 0
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "Il doit rester au moins un administrateur actif")

        retires = []
        if role in SINGLE_HOLDER:
            for old in db.scalars(select(User).where(User.role == role, User.id != user.id).with_for_update()):
                old.role = Role.demandeur
                retires.append(old.cuid)
                audit(
                    db,
                    "USER_UPDATED",
                    actor_id=admin.id,
                    entity="user",
                    entity_id=old.id,
                    request=request,
                    details={
                        "cuid": old.cuid,
                        "ancien_role": role.value,
                        "role": Role.demandeur.value,
                        "remplace_par": user.cuid,
                    },
                    commit=False,
                )

        if role != user.role:
            audit(
                db,
                "USER_UPDATED",
                actor_id=admin.id,
                entity="user",
                entity_id=user.id,
                request=request,
                details={"cuid": user.cuid, "ancien_role": user.role.value, "role": role.value},
                commit=False,
            )
            user.role = role

        db.commit()
        return retires

    @classmethod
    def create_or_assign_by_cuid(
        cls,
        db: Session,
        data: UserCreateIn,
        admin: User,
        request: Request,
    ) -> RoleAssignOut:
        cuid = data.cuid.upper()
        user = db.scalar(select(User).where(User.cuid == cuid))
        if user is None:
            user = User(
                cuid=cuid,
                email=f"{cuid.lower()}{PENDING_EMAIL_DOMAIN}",
                nom=cuid,
                prenom="-",
                telephone="",
                departement="Non renseignee",
                role=Role.demandeur,
                password_hash=NO_LOCAL_PASSWORD,
            )
            db.add(user)
            db.flush()
            audit(
                db,
                "USER_CREATED",
                actor_id=admin.id,
                entity="user",
                entity_id=user.id,
                request=request,
                details={"cuid": cuid, "role": data.role.value},
                commit=False,
            )
        retires = cls.assign_role(db, user, data.role, admin, request)
        return RoleAssignOut(user=UserAdminOut.model_validate(user), retires=retires)

    @classmethod
    def update_role(cls, db: Session, user_id: int, data: UserRoleIn, admin: User, request: Request) -> RoleAssignOut:
        user = cls.get_user(db, user_id)
        retires = cls.assign_role(db, user, data.role, admin, request)
        return RoleAssignOut(user=UserAdminOut.model_validate(user), retires=retires)

    @classmethod
    def set_user_status(
        cls,
        db: Session,
        user_id: int,
        data: UserStatusIn,
        admin: User,
        request: Request,
    ) -> User:
        user = cls.get_user(db, user_id)
        if not data.is_active:
            if user.id == admin.id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas desactiver votre propre compte")
            if user.role == Role.admin and cls.other_active_admins(db, user.id) == 0:
                raise HTTPException(status.HTTP_409_CONFLICT, "Il doit rester au moins un administrateur actif")

        user.is_active = data.is_active
        audit(
            db,
            "USER_ACTIVATED" if data.is_active else "USER_DEACTIVATED",
            actor_id=admin.id,
            entity="user",
            entity_id=user.id,
            request=request,
            details={"cuid": user.cuid},
        )
        return user

    @classmethod
    def list_audit_logs(
        cls,
        db: Session,
        categorie: str | None = None,
        search_term: str | None = None,
        before_id: int | None = None,
        limit: int = 50,
    ) -> list[AuditOut]:
        stmt = (
            select(AuditLog, User)
            .outerjoin(User, AuditLog.actor_id == User.id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        if categorie:
            if categorie not in CATEGORIES:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Categorie inconnue")
            stmt = stmt.where(
                or_(*[AuditLog.action.startswith(p, autoescape=True) for p in CATEGORIES[categorie]])
            )
        if search_term and search_term.strip():
            term = search_term.strip().lower()
            stmt = stmt.where(
                or_(
                    func.lower(User.cuid).contains(term, autoescape=True),
                    func.lower(User.nom).contains(term, autoescape=True),
                    func.lower(AuditLog.details).contains(term, autoescape=True),
                )
            )
        if before_id:
            stmt = stmt.where(AuditLog.id < before_id)

        return [
            AuditOut(
                id=a.id,
                created_at=a.created_at,
                action=a.action,
                acteur=u.display_name if u else None,
                acteur_cuid=u.cuid if u else None,
                entity=a.entity,
                entity_id=a.entity_id,
                ip=a.ip,
                details=a.details,
            )
            for a, u in db.execute(stmt).all()
        ]
