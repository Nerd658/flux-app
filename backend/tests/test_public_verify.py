import os
import secrets

os.environ.update({
    "DATABASE_URL": "sqlite:///./test_flux.db",
    "JWT_SECRET": secrets.token_urlsafe(48),
    "KEY_ENCRYPTION_SECRET": secrets.token_urlsafe(48),
    "SEED_PASSWORD": "Test-Pass-123",
    "AUTH_MODE": "local",
})

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.database import SessionLocal, engine
from app.main import app
from app.models import Decision, FluxLine, FluxRequest, Periode, Role, Statut, User, Validation, utcnow
from app.seal import content_hash, sign_decision

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def db():
    if os.path.exists("test_flux.db"):
        os.remove("test_flux.db")
    seed.run()
    yield
    engine.dispose()
    if os.path.exists("test_flux.db"):
        os.remove("test_flux.db")


def test_public_verify_not_found():
    response = client.get("/api/public/verify?q=NONEXISTENT-REF")
    assert response.status_code == 404
    assert "Aucune demande trouvée" in response.json()["detail"]


def test_public_verify_by_reference_and_ticket_ref():
    session = SessionLocal()
    try:
        manager = session.query(User).filter_by(role=Role.manager).first()
        secu = session.query(User).filter_by(role=Role.securite).first()
        rssi = session.query(User).filter_by(role=Role.rssi).first()
        demandeur = session.query(User).filter_by(role=Role.demandeur).first()

        req = FluxRequest(
            reference="DOF-2026-999999",
            ticket_ref="R-999999",
            flux_type_id=1,
            flux_type_label="Interne",
            dem_nom=demandeur.nom,
            dem_prenom=demandeur.prenom,
            dem_email=demandeur.email,
            dem_telephone=demandeur.telephone,
            mgr_nom=manager.nom,
            mgr_prenom=manager.prenom,
            mgr_email=manager.email,
            mgr_telephone=manager.telephone,
            manager_cuid=manager.cuid,
            departement="Direction Informatique",
            periode=Periode.permanente,
            date_debut=utcnow().date(),
            demandeur_id=demandeur.id,
            statut=Statut.validee,
            content_hash="placeholder",
        )
        session.add(req)
        session.flush()

        line = FluxLine(
            request_id=req.id,
            numero=1,
            src_ip="10.1.2.3",
            src_zone="LAN",
            src_pays="Burkina Faso",
            src_app="App Source",
            dst_ip="192.168.10.20",
            dst_ports="443,8443",
            protocole="TCP",
            dst_zone="DMZ",
            dst_pays="Burkina Faso",
            dst_app="Portail Web",
            type_acces="LAN - DMZ",
            justification="Acces securise au portail web",
        )
        session.add(line)
        session.flush()

        req.content_hash = content_hash(req)

        # Les 3 validations signées
        v1 = Validation(request_id=req.id, niveau=1, validateur_id=manager.id, decision=Decision.validee, decided_at=utcnow())
        v1.validateur = manager
        sign_decision(session, req, v1, manager)
        req.validations.append(v1)

        v2 = Validation(request_id=req.id, niveau=2, validateur_id=secu.id, decision=Decision.validee, decided_at=utcnow())
        v2.validateur = secu
        sign_decision(session, req, v2, secu)
        req.validations.append(v2)

        v3 = Validation(request_id=req.id, niveau=3, validateur_id=rssi.id, decision=Decision.validee, decided_at=utcnow())
        v3.validateur = rssi
        sign_decision(session, req, v3, rssi)
        req.validations.append(v3)

        session.commit()
    finally:
        session.close()

    # 1. Vérification par référence
    res_ref = client.get("/api/public/verify?q=dof-2026-999999")
    assert res_ref.status_code == 200
    data_ref = res_ref.json()
    assert data_ref["reference"] == "DOF-2026-999999"
    assert data_ref["ticket_ref"] == "R-999999"
    assert data_ref["contenu_intact"] is True
    assert data_ref["document_fiable"] is True
    assert len(data_ref["signatures"]) == 3
    assert all(s["signature_valide"] for s in data_ref["signatures"])
    assert len(data_ref["lines"]) == 1
    assert data_ref["lines"][0]["dst_ports"] == "443,8443"

    # 2. Vérification par numéro de ticket Oline
    res_ticket = client.get("/api/public/verify?q=r-999999")
    assert res_ticket.status_code == 200
    data_ticket = res_ticket.json()
    assert data_ticket["reference"] == "DOF-2026-999999"
    assert data_ticket["ticket_ref"] == "R-999999"
    assert data_ticket["document_fiable"] is True
