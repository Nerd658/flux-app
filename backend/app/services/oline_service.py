import logging
from typing import Any

from sqlalchemy.orm import Session

from app.audit import audit
from app.models import FluxRequest
from app.oline import Oline, OlineError
from app.pdf import build_pdf

logger = logging.getLogger("oline")


class OlineService:
    @classmethod
    def _format_description(cls, req: FluxRequest) -> str:
        justifications = []
        for l in req.lines:
            if l.justification and l.justification.strip():
                if len(req.lines) > 1:
                    justifications.append(f"- Flux {l.numero} : {l.justification.strip()}")
                else:
                    justifications.append(l.justification.strip())

        justif_text = "\n".join(justifications) if justifications else "Ouverture de flux réseau validée par le RSSI."

        statut_label = (
            req.dem_statut_pro.value.capitalize()
            if getattr(req, "dem_statut_pro", None)
            else "Employé"
        )

        return (
            f"Demandeur : {req.dem_prenom} {req.dem_nom.upper()} ({statut_label})\n"
            f"Direction : {req.departement}\n"
            f"Justification :\n"
            f"{justif_text}\n\n"
            f"Référence : {req.reference}\n"
            f"Sceau d'intégrité : {req.content_hash}\n\n"
            f"(Le détail complet des règles de flux et des signatures électroniques est consigné dans le document PDF scellé en pièce jointe)"
        )

    @classmethod
    def sync_ticket_on_final_validation(cls, db: Session, req: FluxRequest, request: Any = None) -> str | None:
        """Crée automatiquement le ticket Oline après validation finale par le RSSI."""
        oline = Oline()
        if not oline.url or not oline.api_key:
            logger.info("Oline non configuré (OLINE_URL ou OLINE_API_KEY absent) : création de ticket ignorée")
            return None

        title = f"[Flux] {req.flux_type_label} - {req.reference} - {req.dem_nom.upper()}"
        description = cls._format_description(req)

        ticket = None
        # 1. Tentative avec l'email nominatif du demandeur
        try:
            ticket = oline.create_ticket(
                title=title,
                description=description,
                org_id="Direction Informatique",
                caller_id=req.dem_email,
            )
        except OlineError as e:
            logger.warning("Échec création ticket avec caller_id '%s': %s. Nouvel essai sans caller...", req.dem_email, e)
            try:
                ticket = oline.create_ticket(
                    title=title,
                    description=description,
                    org_id="Direction Informatique",
                    caller_id=None,
                )
            except OlineError as exc:
                logger.error("Impossible de créer le ticket Oline : %s", exc)
                audit(
                    db,
                    "TICKET_CREATION_FAILED",
                    actor_id=None,
                    entity="flux_request",
                    entity_id=req.id,
                    request=request,
                    details={"reference": req.reference, "erreur": str(exc)},
                    commit=False,
                )
                return None

        if not ticket:
            return None

        ticket_id = ticket.get("id") or ticket.get("key")
        ticket_ref = ticket.get("ref") or ticket.get("friendlyname") or str(ticket_id)
        req.ticket_ref = str(ticket_ref)

        # 2. Ajout du PDF scellé et signé électroniquement en pièce jointe
        try:
            from app.services.request_service import RequestService
            detail = RequestService.to_detail(req)
            pdf_bytes = build_pdf(detail)
            oline.add_attachment(
                ticket_id=ticket_id,
                file_bytes=pdf_bytes,
                filename=f"{req.reference}.pdf",
                mimetype="application/pdf",
            )
        except Exception as e:
            logger.warning("Impossible de joindre le PDF au ticket %s : %s", ticket_ref, e)

        audit(
            db,
            "TICKET_CREATED",
            actor_id=None,
            entity="flux_request",
            entity_id=req.id,
            request=request,
            details={"reference": req.reference, "ticket_ref": ticket_ref, "ticket_id": ticket_id},
            commit=False,
        )
        return str(ticket_ref)
