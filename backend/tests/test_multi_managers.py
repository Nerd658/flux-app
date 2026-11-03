import os
import secrets
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.update({
    "DATABASE_URL": "sqlite:///./test_multi_mgr.db",
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
from app.models import Direction, Role, User

PWD = "Test-Pass-123"


@pytest.fixture(scope="module", autouse=True)
def db():
    if os.path.exists("test_multi_mgr.db"):
        os.remove("test_multi_mgr.db")
    seed.run()

    # Creer un deuxieme manager pour les tests
    with SessionLocal() as s:
        existing = s.query(User).filter(User.cuid == "MGR00001").first()
        pwd_hash = existing.password_hash if existing else "dummy"
        m2 = User(
            cuid="MGR00002",
            nom="Ouedraogo",
            prenom="Fatou",
            email="fatou.ouedraogo@orange.com",
            telephone="+226 70 00 00 02",
            departement="DRSI",
            role=Role.manager,
            password_hash=pwd_hash,
        )
        s.add(m2)

        # Ajouter une direction DRSI avec deux managers
        drsi = Direction(
            libelle="DRSI",
            manager_cuid="MGR00001, MGR00002",
        )
        s.add(drsi)
        s.commit()

    yield
    engine.dispose()
    if os.path.exists("test_multi_mgr.db"):
        os.remove("test_multi_mgr.db")


def client(cuid: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"cuid": cuid, "password": PWD}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("csrf_token")
    return c


def sample_payload(**over):
    start = date.today() + timedelta(days=1)
    data = {
        "flux_type_id": 1,
        "manager": {"nom": "Zongo", "prenom": "Paul", "email": "paul.zongo@orange.com", "telephone": "+226 70 11 22 33"},
        "departement": "DRSI",
        "manager_cuid": "MGR00001",
        "periode": "temporaire",
        "date_debut": start.isoformat(),
        "date_fin": (start + timedelta(days=30)).isoformat(),
        "lines": [{
            "src_ip": "10.0.0.5", "src_zone": "Zone1", "src_pays": "Burkina Faso",
            "src_app": "App1", "dst_ip": "192.168.1.10", "dst_ports": "443", "protocole": "TCP",
            "dst_zone": "Zone2", "dst_pays": "Burkina Faso", "dst_app": "App2",
            "justification": "Ouverture flux DRSI",
        }],
    }
    data.update(over)
    return data


def test_referentiels_returns_managers():
    dem = client("LHGL6650")
    res = dem.get("/api/referentiels")
    assert res.status_code == 200
    directions = res.json()["directions"]
    drsi = next(d for d in directions if d["libelle"] == "DRSI")
    assert drsi["manager_cuid"] == "MGR00001, MGR00002"
    assert len(drsi["managers"]) == 2
    cuids = [m["cuid"] for m in drsi["managers"]]
    assert "MGR00001" in cuids
    assert "MGR00002" in cuids


def test_submission_with_authorized_manager():
    dem = client("LHGL6650")
    # Selection du second manager autorise
    res = dem.post("/api/requests/", json=sample_payload(manager_cuid="MGR00002"))
    assert res.status_code == 201
    data = res.json()
    assert data["manager_cuid"] == "MGR00002"
    assert data["manager"]["nom"] == "Ouedraogo"
    assert data["manager"]["prenom"] == "Fatou"


def test_submission_with_unauthorized_manager_rejected():
    dem = client("LHGL6650")
    # CUID qui n'est pas autorise pour la DRSI
    res = dem.post("/api/requests/", json=sample_payload(manager_cuid="RSSI0001"))
    assert res.status_code == 400
    assert "n'est pas habilité pour la direction DRSI" in res.json()["detail"]


def test_submission_self_validation_rejected():
    # Un demandeur qui essaie de se designer lui-meme comme manager
    dem = client("LHGL6650")
    res = dem.post("/api/requests/", json=sample_payload(manager_cuid="LHGL6650"))
    assert res.status_code == 400
    assert "n'est pas habilité pour la direction DRSI" in res.json()["detail"] or "Vous ne pouvez pas vous désigner vous-même" in res.json()["detail"]


def test_submission_colleague_not_manager_rejected():
    dem = client("LHGL6650")
    # Creer une direction autorisant un demandeur lambda
    adm = client("ADMN0001")
    adm.post("/api/admin/referentiels/directions", json={"libelle": "Direction Test", "manager_cuid": "LHGL6650"})

    # Tenter de soumettre avec ce demandeur comme manager
    # Note: comme LHGL6650 est le demandeur actuel, c'est rejete pour auto-designation.
    res = dem.post("/api/requests/", json=sample_payload(departement="Direction Test", manager_cuid="LHGL6650"))
    assert res.status_code == 400
