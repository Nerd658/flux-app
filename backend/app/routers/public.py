from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import FluxRequest, Statut, Validation
from app.schemas import FluxLineOut, PublicSignatureOut, PublicVerifyOut
from app.seal import verify_request

router = APIRouter(prefix="/api/public", tags=["public"])

ROLE_LABELS = {
    1: "Manager de département",
    2: "Validateur Technique (Sécurité)",
    3: "RSSI (Validation finale)",
}


@router.get("/verify", response_model=PublicVerifyOut)
def verify_request_public(
    q: str = Query(..., min_length=2, max_length=100, description="Référence ou numéro de ticket Oline"),
    db: Session = Depends(get_db),
):
    query_str = q.strip()
    stmt = (
        select(FluxRequest)
        .where(
            or_(
                func.lower(FluxRequest.reference) == query_str.lower(),
                func.lower(FluxRequest.ticket_ref) == query_str.lower(),
            )
        )
        .options(
            selectinload(FluxRequest.lines),
            selectinload(FluxRequest.validations).selectinload(Validation.validateur),
        )
    )
    req = db.scalar(stmt)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune demande trouvée pour cette référence ou ce numéro de ticket.",
        )

    seal_res = verify_request(db, req)
    sig_map = {s["niveau"]: s["signature_valide"] for s in seal_res["signatures"]}

    signatures_out = []
    for v in sorted(req.validations, key=lambda x: x.niveau):
        signatures_out.append(
            PublicSignatureOut(
                niveau=v.niveau,
                role_label=ROLE_LABELS.get(v.niveau, f"Niveau {v.niveau}"),
                validateur_nom=v.validateur.display_name if v.validateur else f"Validateur #{v.validateur_id}",
                decision=v.decision,
                decided_at=v.decided_at,
                key_fingerprint=v.key_fingerprint,
                signature_valide=sig_map.get(v.niveau, False),
            )
        )

    lines_out = [FluxLineOut.model_validate(l, from_attributes=True) for l in req.lines]

    return PublicVerifyOut(
        reference=req.reference,
        ticket_ref=req.ticket_ref,
        flux_type=req.flux_type_label,
        statut=req.statut,
        demandeur_nom=f"{req.dem_prenom} {req.dem_nom.upper()}",
        demandeur_statut_pro=getattr(req, "dem_statut_pro", None),
        direction=getattr(req, "direction", "") or "",
        departement=req.departement,
        periode=req.periode,
        date_debut=req.date_debut,
        date_fin=req.date_fin,
        content_hash=req.content_hash,
        contenu_intact=seal_res["contenu_intact"],
        document_fiable=seal_res["document_fiable"] and req.statut == Statut.validee,
        signatures=signatures_out,
        lines=lines_out,
    )
