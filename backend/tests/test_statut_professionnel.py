import os
import secrets
from datetime import date, timedelta
from unittest.mock import MagicMock

os.environ.update({
    "DATABASE_URL": "sqlite:///./test_statut.db",
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
from app.models import FluxRequest, Role, StatutProfessionnel, User
from app.schemas import UserOut
from app.services.oline_service import OlineService

PWD = "Test-Pass-123"


@pytest.fixture(scope="module", autouse=True)
def db():
    if os.path.exists("test_statut.db"):
        os.remove("test_statut.db")
    seed.run()
    yield
    engine.dispose()
    if os.path.exists("test_statut.db"):
        os.remove("test_statut.db")


def client(cuid: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"cuid": cuid, "password": PWD}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("csrf_token")
    return c


def test_profil_incomplet_when_statut_pro_none():
    u = UserOut(
        id=1,
        cuid="TEST0001",
        email="test@orange.bf",
        nom="Dupont",
        prenom="Jean",
        telephone="+22670000000",
        departement="Direction CX",
        role=Role.demandeur,
        statut_pro=None,
    )
    assert u.profil_incomplet is True

    u_complete = UserOut(
        id=1,
        cuid="TEST0001",
        email="test@orange.bf",
        nom="Dupont",
        prenom="Jean",
        telephone="+22670000000",
        departement="Direction CX",
        role=Role.demandeur,
        statut_pro=StatutProfessionnel.prestataire,
    )
    assert u_complete.profil_incomplet is False


def test_api_update_profile_and_me():
    c = client("DEMD0001")
    # Mettre à jour le profil avec statut_pro prestataire
    r = c.put(
        "/api/auth/profile",
        json={
            "nom": "Ouedraogo",
            "prenom": "Awa",
            "email": "awa.ouedraogo@fluxapp.bf",
            "telephone": "+22670000001",
            "departement": "CX",
            "statut_pro": "prestataire",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["statut_pro"] == "prestataire"
    assert body["profil_incomplet"] is False

    # Vérifier /api/auth/me
    me = c.get("/api/auth/me").json()
    assert me["statut_pro"] == "prestataire"


def test_api_request_submission_freezes_statut_pro():
    c = client("DEMD0001")
    start = (date.today() + timedelta(days=1)).isoformat()
    req_payload = {
        "flux_type_id": 1,
        "departement": "CX",
        "manager_cuid": "MGR00001",
        "manager": {
            "nom": "Traore",
            "prenom": "Moussa",
            "email": "moussa.traore@fluxapp.bf",
            "telephone": "+22670000005",
        },
        "periode": "permanente",
        "date_debut": start,
        "date_fin": None,
        "lines": [
            {
                "src_ip": "10.1.1.1",
                "src_zone": "Zone1",
                "src_pays": "Burkina Faso",
                "src_app": "ERP",
                "dst_ip": "10.2.2.2",
                "dst_ports": "443",
                "protocole": "TCP",
                "dst_zone": "Zone2",
                "dst_pays": "Burkina Faso",
                "dst_app": "DB",
                "justification": "Synchro DB",
            }
        ],
    }
    r = c.post("/api/requests/", json=req_payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["demandeur"]["statut_pro"] == "prestataire"

    # Vérifier directement dans la base de données
    with SessionLocal() as db:
        req = db.get(FluxRequest, data["id"])
        assert req.dem_statut_pro == StatutProfessionnel.prestataire


def test_oline_description_includes_statut_pro():
    req = MagicMock(spec=FluxRequest)
    req.dem_nom = "Traore"
    req.dem_prenom = "Salif"
    req.departement = "Direction CX"
    req.dem_statut_pro = StatutProfessionnel.prestataire
    req.lines = []
    req.reference = "DOF-2026-0001"
    req.content_hash = "1234567890abcdef"

    desc = OlineService._format_description(req)
    assert "Demandeur : Salif TRAORE (Prestataire)" in desc
    assert "Direction : Direction CX" in desc
