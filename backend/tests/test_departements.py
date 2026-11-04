"""Tests de la hiérarchie Direction > Département et de l'habilitation du manager de département."""
import os
import secrets
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.update({
    "DATABASE_URL": "sqlite:///./test_depts.db",
    "JWT_SECRET": secrets.token_urlsafe(48),
    "KEY_ENCRYPTION_SECRET": secrets.token_urlsafe(48),
    "SEED_PASSWORD": "Test-Pass-123",
    "AUTH_MODE": "local",
})

from app import seed  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Departement, Direction, FluxRequest, Role, User  # noqa: E402

PWD = "Test-Pass-123"


@pytest.fixture(scope="module", autouse=True)
def db():
    if os.path.exists("test_depts.db"):
        os.remove("test_depts.db")
    seed.run()

    with SessionLocal() as s:
        # Creer un utilisateur manager additionnel
        existing = s.query(User).filter(User.cuid == "MGR00001").first()
        pwd_hash = existing.password_hash if existing else "dummy"
        m_sec = User(
            cuid="MGR00009",
            nom="Diallo",
            prenom="Amadou",
            email="amadou.diallo@fluxapp.bf",
            telephone="+22670000009",
            direction="DRSI",
            departement="Securite SI",
            role=Role.manager,
            password_hash=pwd_hash,
        )
        s.add(m_sec)

        # Creer une direction DRSI et ses departements
        drsi = Direction(libelle="DRSI", manager_cuid="MGR00001")
        s.add(drsi)
        s.flush()

        dept1 = Departement(direction_id=drsi.id, libelle="Securite SI", manager_cuid="MGR00009")
        dept2 = Departement(direction_id=drsi.id, libelle="Infrastructure Reseau", manager_cuid="MGR00001")
        s.add_all([dept1, dept2])
        s.commit()

    yield
    engine.dispose()
    if os.path.exists("test_depts.db"):
        os.remove("test_depts.db")


def client(cuid: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"cuid": cuid, "password": PWD}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("csrf_token")
    return c


def sample_payload(**over):
    start = date.today() + timedelta(days=1)
    data = {
        "flux_type_id": 1,
        "manager": {"nom": "Diallo", "prenom": "Amadou", "email": "amadou.diallo@fluxapp.bf", "telephone": "+22670000009"},
        "direction": "DRSI",
        "departement": "Securite SI",
        "manager_cuid": "MGR00009",
        "periode": "temporaire",
        "date_debut": start.isoformat(),
        "date_fin": (start + timedelta(days=30)).isoformat(),
        "lines": [{
            "src_ip": "10.0.0.5", "src_zone": "Zone1", "src_pays": "Burkina Faso",
            "src_app": "App1", "dst_ip": "192.168.1.10", "dst_ports": "443", "protocole": "TCP",
            "dst_zone": "Zone2", "dst_pays": "Burkina Faso", "dst_app": "App2",
            "justification": "Ouverture flux Securite SI",
        }],
    }
    data.update(over)
    return data


def test_referentiels_returns_directions_and_departements():
    dem = client("DEMD0001")
    res = dem.get("/api/referentiels")
    assert res.status_code == 200
    body = res.json()
    assert "directions" in body
    assert "departements" in body

    # Verifier que les departements sont bien lies a la DRSI
    drsi_depts = [d for d in body["departements"] if d["direction_libelle"] == "DRSI"]
    assert len(drsi_depts) >= 2
    sec_dept = next(d for d in drsi_depts if d["libelle"] == "Securite SI")
    assert sec_dept["manager_cuid"] == "MGR00009"
    assert len(sec_dept["managers"]) == 1
    assert sec_dept["managers"][0]["cuid"] == "MGR00009"


def test_admin_manage_departement():
    adm = client("ADMN0001")
    # Creation d'un nouveau departement via admin
    with SessionLocal() as s:
        drsi_id = s.query(Direction.id).filter(Direction.libelle == "DRSI").scalar()

    res = adm.post("/api/admin/referentiels/departements", json={
        "libelle": "Developpement Applications",
        "direction_id": drsi_id,
        "manager_cuid": "MGR00001",
    })
    assert res.status_code == 201
    created_id = res.json()["id"]

    # Modification du departement
    res_up = adm.put(f"/api/admin/referentiels/departements/{created_id}", json={
        "libelle": "Dev SI & Applications",
        "direction_id": drsi_id,
        "manager_cuid": "MGR00001, MGR00009",
    })
    assert res_up.status_code == 200
    assert res_up.json()["libelle"] == "Dev SI & Applications"
    assert len(res_up.json()["managers"]) == 2

    # Suppression du departement
    res_del = adm.delete(f"/api/admin/referentiels/departements/{created_id}")
    assert res_del.status_code == 204


def test_submission_with_department_manager_success_and_validation():
    dem = client("DEMD0001")
    mgr9 = client("MGR00009")

    # Soumission adressee au manager du departement Securite SI
    res = dem.post("/api/requests", json=sample_payload())
    assert res.status_code == 201
    req_data = res.json()
    req_id = req_data["id"]
    assert req_data["direction"] == "DRSI"
    assert req_data["departement"] == "Securite SI"
    assert req_data["manager_cuid"] == "MGR00009"

    # MGR00009 doit voir la demande en attente
    pending = mgr9.get("/api/requests/pending").json()
    assert any(p["id"] == req_id for p in pending)

    # MGR00009 peut valider au Niveau 1
    res_val = mgr9.post(f"/api/requests/{req_id}/decision", json={"decision": "validee", "commentaire": "Accord Dept"})
    assert res_val.status_code == 200
    assert res_val.json()["statut"] == "validee_manager"


def test_submission_with_unauthorized_manager_for_dept_rejected():
    dem = client("DEMD0001")
    # Tentative d'assigner un manager non habilite pour Securite SI (ex: MGR00001 au lieu de MGR00009)
    res = dem.post("/api/requests", json=sample_payload(manager_cuid="MGR00001"))
    assert res.status_code == 400
    assert "n'est pas habilité pour le département Securite SI" in res.json()["detail"]
