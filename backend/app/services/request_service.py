import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.common.dates import to_naive_utc
from app.models import (
    Decision,
    Direction,
    FluxLine,
    FluxRequest,
    Role,
    Statut,
    User,
    Validation,
    utcnow,
)
from app.pdf import build_pdf
from app.schemas import (
    DecisionIn,
    FluxRequestIn,
    PersonneOut,
    RequestDetail,
    RequestSummary,
    ValidationOut,
    ValidatorStatsOut,
    VerifyOut,
)
from app.seal import content_hash, sign_decision, verify_request
from app.services.referential_service import ReferentialService

VALIDATORS = (
    Role.manager,
    Role.securite,
    Role.rssi,
    Role.admin,
)

TRANSITIONS = {
    Role.manager: (Statut.soumise, 1, Statut.validee_manager, Statut.refusee),
    Role.securite: (Statut.validee_manager, 2, Statut.validee_technique, Statut.refusee),
    Role.rssi: (Statut.validee_technique, 3, Statut.validee, Statut.refusee),
}

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable")


class RequestService:
    @staticmethod
    def load(db: Session, request_id: int, lock: bool = False) -> FluxRequest:
        stmt = (
            select(FluxRequest)
            .where(FluxRequest.id == request_id)
            .options(
                selectinload(FluxRequest.lines),
                selectinload(FluxRequest.validations).selectinload(Validation.validateur),
            )
        )
        if lock:
            stmt = stmt.with_for_update()
        req = db.scalar(stmt)
        if not req:
            raise _NOT_FOUND
        return req

    @staticmethod
    def check_access(user: User, req: FluxRequest) -> None:
        if user.role not in VALIDATORS and req.demandeur_id != user.id:
            raise _NOT_FOUND
        if user.role == Role.manager and req.demandeur_id != user.id:
            if req.manager_cuid and req.manager_cuid != user.cuid:
                raise _NOT_FOUND

    @classmethod
    def to_detail(cls, req: FluxRequest) -> RequestDetail:
        return RequestDetail(
            id=req.id,
            reference=req.reference,
            statut=req.statut,
            created_at=req.created_at,
            content_hash=req.content_hash,
            flux_type=req.flux_type_label,
            demandeur=PersonneOut(
                nom=req.dem_nom,
                prenom=req.dem_prenom,
                email=req.dem_email,
                telephone=req.dem_telephone,
            ),
            manager=PersonneOut(
                nom=req.mgr_nom,
                prenom=req.mgr_prenom,
                email=req.mgr_email,
                telephone=req.mgr_telephone,
            ),
            manager_cuid=req.manager_cuid,
            departement=req.departement,
            periode=req.periode,
            date_debut=req.date_debut,
            date_fin=req.date_fin,
            lines=req.lines,
            validations=[
                ValidationOut(
                    niveau=v.niveau,
                    validateur=v.validateur.display_name if v.validateur else f"Validateur #{v.validateur_id}",
                    decision=v.decision,
                    commentaire=v.commentaire,
                    decided_at=v.decided_at,
                    key_fingerprint=v.key_fingerprint,
                )
                for v in req.validations
            ],
        )

    @staticmethod
    def to_summaries(rows) -> list[RequestSummary]:
        return [
            RequestSummary(
                id=r.id,
                reference=r.reference,
                flux_type=r.flux_type_label,
                demandeur=f"{r.dem_prenom} {r.dem_nom.upper()}",
                statut=r.statut,
                created_at=r.created_at,
                nb_lignes=len(r.lines),
            )
            for r in rows
        ]

    @classmethod
    def preview(cls, db: Session, data: FluxRequestIn, user: User) -> RequestDetail:
        flux_label = ReferentialService.validate_request_labels(db, data)
        direction = db.scalar(select(Direction).where(Direction.libelle == data.departement))
        mgr_cuid = direction.manager_cuid if direction and direction.manager_cuid else data.manager_cuid
        return RequestDetail(
            flux_type=flux_label,
            demandeur=PersonneOut(
                nom=user.nom, prenom=user.prenom, email=user.email, telephone=user.telephone
            ),
            manager=PersonneOut(**data.manager.model_dump()),
            manager_cuid=mgr_cuid,
            departement=data.departement,
            periode=data.periode,
            date_debut=data.date_debut,
            date_fin=data.date_fin,
            lines=[{"numero": i, **l.model_dump()} for i, l in enumerate(data.lines, start=1)],
        )

    @classmethod
    def submit(cls, db: Session, data: FluxRequestIn, user: User, request: Request) -> RequestDetail:
        flux_label = ReferentialService.validate_request_labels(db, data)
        direction = db.scalar(select(Direction).where(Direction.libelle == data.departement))
        mgr_cuid = direction.manager_cuid if direction and direction.manager_cuid else data.manager_cuid
        if mgr_cuid:
            mgr_cuid = mgr_cuid.strip().upper()

        req = FluxRequest(
            reference=f"TMP-{secrets.token_hex(8)}",
            flux_type_id=data.flux_type_id,
            flux_type_label=flux_label,
            demandeur_id=user.id,
            dem_nom=user.nom,
            dem_prenom=user.prenom,
            dem_email=user.email,
            dem_telephone=user.telephone,
            departement=data.departement,
            manager_cuid=mgr_cuid,
            mgr_nom=data.manager.nom,
            mgr_prenom=data.manager.prenom,
            mgr_email=str(data.manager.email),
            mgr_telephone=data.manager.telephone,
            periode=data.periode,
            date_debut=data.date_debut,
            date_fin=data.date_fin,
            statut=Statut.soumise,
            content_hash="",
            lines=[FluxLine(numero=i, **l.model_dump()) for i, l in enumerate(data.lines, start=1)],
        )
        db.add(req)
        db.flush()
        req.reference = f"DOF-{req.created_at.year}-{req.id:06d}"
        req.content_hash = content_hash(req)
        audit(
            db,
            "REQUEST_SUBMITTED",
            actor_id=user.id,
            entity="flux_request",
            entity_id=req.id,
            request=request,
            details={"reference": req.reference, "lignes": len(req.lines)},
        )
        return cls.to_detail(req)

    @classmethod
    def list_mine(cls, db: Session, user: User) -> list[RequestSummary]:
        rows = db.scalars(
            select(FluxRequest)
            .where(FluxRequest.demandeur_id == user.id)
            .options(selectinload(FluxRequest.lines))
            .order_by(FluxRequest.created_at.desc())
        )
        return cls.to_summaries(rows)

    @classmethod
    def list_pending(cls, db: Session, user: User) -> list[RequestSummary]:
        if user.role == Role.manager:
            stmt = (
                select(FluxRequest)
                .where(
                    FluxRequest.statut == Statut.soumise,
                    FluxRequest.manager_cuid == user.cuid,
                )
                .options(selectinload(FluxRequest.lines))
                .order_by(FluxRequest.created_at)
            )
        elif user.role in TRANSITIONS:
            expected = TRANSITIONS[user.role][0]
            stmt = (
                select(FluxRequest)
                .where(FluxRequest.statut == expected)
                .options(selectinload(FluxRequest.lines))
                .order_by(FluxRequest.created_at)
            )
        else:
            stmt = select(FluxRequest).where(FluxRequest.id == -1)
        rows = db.scalars(stmt)
        return cls.to_summaries(rows)

    @classmethod
    def list_all(cls, db: Session) -> list[RequestSummary]:
        rows = db.scalars(
            select(FluxRequest)
            .options(selectinload(FluxRequest.lines))
            .order_by(FluxRequest.created_at.desc())
            .limit(500)
        )
        return cls.to_summaries(rows)

    @classmethod
    def get_validator_stats(cls, db: Session, user: User) -> ValidatorStatsOut:
        now = to_naive_utc(datetime.now(timezone.utc))
        if user.role == Role.manager:
            waiting = select(func.count()).select_from(FluxRequest).where(
                FluxRequest.statut == Statut.soumise,
                FluxRequest.manager_cuid == user.cuid,
            )
        elif user.role in TRANSITIONS:
            expected = TRANSITIONS[user.role][0]
            waiting = select(func.count()).select_from(FluxRequest).where(FluxRequest.statut == expected)
        else:
            waiting = select(func.count()).select_from(FluxRequest).where(FluxRequest.id == -1)

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        def decided(decision: Decision) -> int:
            return db.scalar(
                select(func.count())
                .select_from(Validation)
                .where(
                    Validation.validateur_id == user.id,
                    Validation.decision == decision,
                    Validation.decided_at >= month_start,
                )
            )

        return ValidatorStatsOut(
            a_traiter=db.scalar(waiting),
            en_retard=db.scalar(waiting.where(FluxRequest.created_at < now - timedelta(hours=48))),
            validees_mois=decided(Decision.validee),
            refusees_mois=decided(Decision.refusee),
        )

    @classmethod
    def decide(
        cls,
        db: Session,
        request_id: int,
        data: DecisionIn,
        user: User,
        request: Request,
    ) -> RequestDetail:
        req = cls.load(db, request_id, lock=True)
        if user.role not in TRANSITIONS:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Votre rôle ne permet pas de valider des demandes")
        expected, niveau, ok_status, ko_status = TRANSITIONS[user.role]
        if req.statut != expected:
            raise HTTPException(status.HTTP_409_CONFLICT, "La demande n'est pas a votre niveau de validation")
        if user.role == Role.manager and req.manager_cuid and req.manager_cuid != user.cuid:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette demande n'est pas adressee a votre departement")
        if req.demandeur_id == user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas valider votre propre demande")
        if any(v.validateur_id == user.id for v in req.validations):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous avez deja statue sur cette demande")

        v = Validation(
            request_id=req.id,
            niveau=niveau,
            validateur_id=user.id,
            decision=data.decision,
            commentaire=data.commentaire or None,
            decided_at=utcnow().replace(microsecond=0),
        )
        v.validateur = user
        if sign_decision(db, req, v, user):
            audit(
                db,
                "SIGNING_KEY_ISSUED",
                actor_id=user.id,
                entity="user",
                entity_id=user.id,
                request=request,
                commit=False,
            )
        req.validations.append(v)
        req.statut = ok_status if data.decision == Decision.validee else ko_status
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Decision deja enregistree") from None

        audit(
            db,
            f"REQUEST_{data.decision.value.upper()}_N{niveau}",
            actor_id=user.id,
            entity="flux_request",
            entity_id=req.id,
            request=request,
            details={"reference": req.reference, "signed_hash": v.signed_hash},
        )
        return cls.to_detail(req)

    @classmethod
    def verify(cls, db: Session, request_id: int, user: User) -> VerifyOut:
        req = cls.load(db, request_id)
        cls.check_access(user, req)
        return verify_request(db, req)

    @classmethod
    def download_pdf(cls, db: Session, request_id: int, user: User, request: Request) -> Response:
        req = cls.load(db, request_id)
        cls.check_access(user, req)
        if req.statut != Statut.validee:
            raise HTTPException(status.HTTP_409_CONFLICT, "PDF disponible apres validation finale")

        check = verify_request(db, req)
        if not check["document_fiable"]:
            audit(
                db,
                "SEAL_BROKEN",
                actor_id=user.id,
                entity="flux_request",
                entity_id=req.id,
                request=request,
                details={"reference": req.reference},
            )
            raise HTTPException(status.HTTP_409_CONFLICT, "Integrite du document compromise")

        pdf_bytes = build_pdf(cls.to_detail(req))
        audit(
            db,
            "PDF_DOWNLOADED",
            actor_id=user.id,
            entity="flux_request",
            entity_id=req.id,
            request=request,
            details={"reference": req.reference},
        )
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{req.reference}.pdf"'},
        )
