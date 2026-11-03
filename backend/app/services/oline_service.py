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
        lines_desc = []
        for l in req.lines:
            ports = f" Ports: {l.dst_ports}" if l.dst_ports else ""
            lines_desc.append(
                f"- Ligne {l.numero}: [{l.src_ip}] ({l.src_zone}) -> [{l.dst_ip}] ({l.dst_zone}) "
                f"| Proto: {l.protocole}{ports} | Accès: {l.type_acces} | App: {l.dst_app} "
                f"| Justif: {l.justification}"
            )
        flows_text = "\n".join(lines_desc)

        validations_desc = []
        labels = {1: "Manager de département", 2: "Validateur Technique", 3: "RSSI"}
        for v in req.validations:
            validations_desc.append(
                f"- {labels.get(v.niveau, f'Niveau {v.niveau}')} ({v.validateur.display_name if v.validateur else 'Validateur'}): "
                f"{v.decision.value.upper()} le {v.decided_at.strftime('%d/%m/%Y %H:%M UTC')}"
            )
        val_text = "\n".join(validations_desc)

        dates_text = (
            f"Du {req.date_debut} au {req.date_fin}"
            if req.periode.value == "temporaire"
            else f"À partir du {req.date_debut} (Permanente)"
        )

        return (
            f"DEMANDE D'OUVERTURE DE FLUX : {req.reference}\n"
            f"Type d'ouverture : {req.flux_type_label}\n"
            f"Demandeur : {req.dem_prenom} {req.dem_nom.upper()} ({req.dem_email} - {req.dem_telephone})\n"
            f"Direction : {req.departement}\n"
            f"Manager : {req.mgr_prenom} {req.mgr_nom.upper()} ({req.mgr_email})\n"
            f"Période : {dates_text}\n"
            f"Sceau d'intégrité SHA-256 : {req.content_hash}\n\n"
            f"VALIDATIONS EFFECTUÉES :\n{val_text}\n\n"
            f"FLUX RÉSEAU DEMANDÉS ({len(req.lines)}) :\n{flows_text}\n\n"
            f"(Document officiel PDF avec signatures électroniques Ed25519 joint en pièce jointe du ticket)"
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
