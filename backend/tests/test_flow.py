"""Parcours complet sur une base SQLite temporaire : soumission -> N1 -> final -> PDF -> sceau."""
import os
import secrets
from datetime import date, timedelta

os.environ.update({
    "DATABASE_URL": "sqlite:///./test_flux.db",
    "JWT_SECRET": secrets.token_urlsafe(48),
    "KEY_ENCRYPTION_SECRET": secrets.token_urlsafe(48),
    "SEED_PASSWORD": "Test-Pass-123",
    "AUTH_MODE": "local",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sqlalchemy import select

from app import seed  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FluxLine, FluxRequest, User  # noqa: E402

PWD = "Test-Pass-123"


@pytest.fixture(scope="module", autouse=True)
def db():
    if os.path.exists("test_flux.db"):
        os.remove("test_flux.db")
    seed.run()
    yield
    engine.dispose()
    if os.path.exists("test_flux.db"):
        os.remove("test_flux.db")


def client(cuid: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"cuid": cuid, "password": PWD}).status_code == 200
    c.headers["X-CSRF-Token"] = c.cookies.get("csrf_token")
    return c


def payload(**over):
    start = date.today() + timedelta(days=1)
    data = {
        "flux_type_id": 1,
        "manager": {"nom": "Zongo", "prenom": "Paul", "email": "paul.zongo@fluxapp.bf", "telephone": "+226 70 11 22 33"},
        "departement": "CX",
        "periode": "temporaire",
        "date_debut": start.isoformat(),
        "date_fin": (start + timedelta(days=30)).isoformat(),
        "lines": [{
            "src_ip": "10.0.0.5, 10.0.1.0/24", "src_zone": "Zone1", "src_pays": "Burkina Faso",
            "src_app": "CRM", "dst_ip": "192.168.1.10", "dst_ports": "443,8080-8090", "protocole": "TCP",
            "dst_zone": "Zone2", "dst_pays": "Burkina Faso", "dst_app": "https://api.interne",
            "justification": "Synchronisation des données clients",
        }],
    }
    data.update(over)
    return data


def test_login_cuid():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"cuid": "demd0001", "password": PWD}).status_code == 200  # casse ignorée
    assert c.post("/api/auth/login", json={"cuid": "DEMD0001", "password": "faux"}).status_code == 401
    assert c.post("/api/auth/login", json={"cuid": "DEMD' OR 1=1", "password": PWD}).status_code == 422
    assert c.get("/api/auth/me").json()["cuid"] == "DEMD0001"


def test_validation_errors():
    c = client("DEMD0001")
    bad_ip = payload()
    bad_ip["lines"][0]["src_ip"] = "999.1.1.1"
    assert c.post("/api/requests/preview", json=bad_ip).status_code == 422
    bad_port = payload()
    bad_port["lines"][0]["dst_ports"] = "70000"
    assert c.post("/api/requests/preview", json=bad_port).status_code == 422
    bad_proto = payload()
    bad_proto["lines"][0]["protocole"] = "TCP;DROP"
    assert c.post("/api/requests/preview", json=bad_proto).status_code == 422
    # Protocole libre normalisé en majuscules ; ports obligatoires, sauf pour ICMP
    free = payload()
    free["lines"][0].update(protocole="tcp/udp", dst_ports="53")
    assert c.post("/api/requests/preview", json=free).json()["lines"][0]["protocole"] == "TCP/UDP"
    no_port = payload()
    no_port["lines"][0].update(protocole="TCP", dst_ports="")
    assert c.post("/api/requests/preview", json=no_port).status_code == 422
    icmp = payload()
    icmp["lines"][0].update(protocole="icmp", dst_ports="")
    line = c.post("/api/requests/preview", json=icmp).json()["lines"][0]
    assert line["protocole"] == "ICMP" and line["dst_ports"] == ""
    bad_zone = payload()
    bad_zone["lines"][0]["dst_zone"] = "ZoneX"
    assert c.post("/api/requests/preview", json=bad_zone).status_code == 422
    assert c.post("/api/requests/preview", json=payload(date_fin=None)).status_code == 422
    # Sans jeton CSRF : refus
    del c.headers["X-CSRF-Token"]
    assert c.post("/api/requests/preview", json=payload()).status_code == 403


def test_directions():
    c = client("DEMD0001")
    assert {"CX", "RSSI"} <= {d["libelle"] for d in c.get("/api/referentiels").json()["directions"]}
    assert c.post("/api/requests/preview", json=payload(departement="Inconnue")).status_code == 422
    assert c.post("/api/referentiels/directions", json={"libelle": "DSI"}).status_code == 201
    assert c.post("/api/referentiels/directions", json={"libelle": "dsi"}).status_code == 409
    assert c.post("/api/requests/preview", json=payload(departement="DSI")).status_code == 200


def test_add_flux_type():
    c = client("DEMD0001")
    assert c.post("/api/referentiels/flux-types", json={"libelle": "VPN partenaire"}).status_code == 201
    assert c.post("/api/referentiels/flux-types", json={"libelle": "vpn PARTENAIRE"}).status_code == 409
    labels = [t["libelle"] for t in c.get("/api/referentiels").json()["flux_types"]]
    assert {"HA", "Internet", "VPN partenaire"} <= set(labels)


def test_full_flow():
    dem, mgr, secu, rssi = client("DEMD0001"), client("MGR00001"), client("SECU0001"), client("RSSI0001")

    recap = dem.post("/api/requests/preview", json=payload()).json()
    assert recap["lines"][0]["src_ip"] == "10.0.0.5, 10.0.1.0/24" and recap["id"] is None

    r = dem.post("/api/requests", json=payload())
    assert r.status_code == 201
    rid, ref = r.json()["id"], r.json()["reference"]
    assert ref.startswith("DOF-")

    # Le validateur technique ne peut pas passer avant le manager ; le RSSI ne peut pas passer avant le technique
    assert secu.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).status_code == 409
    assert rssi.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).status_code == 409
    assert dem.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).status_code == 403
    # PDF indisponible avant validation finale
    assert dem.get(f"/api/requests/{rid}/pdf").status_code == 409

    # Étape 1 : Manager de département
    assert rid in [x["id"] for x in mgr.get("/api/requests/pending").json()]
    assert mgr.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).json()["statut"] == "validee_manager"
    assert mgr.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).status_code == 409

    # Étape 2 : Validateur technique (sécurité)
    assert rid in [x["id"] for x in secu.get("/api/requests/pending").json()]
    assert secu.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).json()["statut"] == "validee_technique"
    assert secu.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).status_code == 409

    # Étape 3 : RSSI
    assert rid in [x["id"] for x in rssi.get("/api/requests/pending").json()]
    assert rssi.post(f"/api/requests/{rid}/decision", json={"decision": "validee"}).json()["statut"] == "validee"

    mine = dem.get("/api/requests/mine").json()
    assert mine[0]["statut"] == "validee"
    assert dem.get(f"/api/requests/{rid}/verify").json()["document_fiable"] is True

    pdf = dem.get(f"/api/requests/{rid}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    with open("test_output.pdf", "wb") as f:
        f.write(pdf.content)

    # Altération directe en base -> sceau rompu, PDF refusé
    with SessionLocal() as s, s.begin():
        line = s.query(FluxLine).filter_by(request_id=rid).one()
        line.dst_ports = "1-65535"
    check = dem.get(f"/api/requests/{rid}/verify").json()
    assert check["contenu_intact"] is False and check["document_fiable"] is False
    assert dem.get(f"/api/requests/{rid}/pdf").status_code == 409


def test_refusal_requires_comment_and_idor():
    dem, mgr = client("DEMD0001"), client("MGR00001")
    rid = dem.post("/api/requests", json=payload()).json()["id"]
    assert mgr.post(f"/api/requests/{rid}/decision", json={"decision": "refusee"}).status_code == 422
    r = mgr.post(f"/api/requests/{rid}/decision", json={"decision": "refusee", "commentaire": "Port trop large"})
    assert r.json()["statut"] == "refusee"
    assert dem.get(f"/api/requests/{rid}").json()["validations"][0]["commentaire"] == "Port trop large"

    # Un autre demandeur ne voit pas la demande (anti-IDOR)
    with SessionLocal() as s, s.begin():
        req = s.get(FluxRequest, rid)
        req.demandeur_id = 4    # réattribuée à l'admin pour simuler un tiers
    assert dem.get(f"/api/requests/{rid}").status_code == 404


def test_master_key_change_rotates_signing_key():
    """Après un changement de KEY_ENCRYPTION_SECRET : pas d'erreur, nouvelle clé, anciennes signatures valides."""
    from app.config import get_settings
    dem, mgr = client("DEMD0001"), client("MGR00001")
    first = dem.post("/api/requests", json=payload()).json()["id"]
    assert mgr.post(f"/api/requests/{first}/decision", json={"decision": "validee"}).status_code == 200

    settings = get_settings()
    old = settings.key_encryption_secret
    settings.key_encryption_secret = secrets.token_urlsafe(48)       # simule un .env modifié
    try:
        second = dem.post("/api/requests", json=payload()).json()["id"]
        r = mgr.post(f"/api/requests/{second}/decision", json={"decision": "refusee", "commentaire": "Motif de test"})
        assert r.status_code == 200
        assert dem.get(f"/api/requests/{first}/verify").json()["document_fiable"] is True
        assert dem.get(f"/api/requests/{second}/verify").json()["document_fiable"] is True
    finally:
        settings.key_encryption_secret = old


# ---------- Espace administrateur ----------

def test_admin_is_admin_only():
    assert client("DEMD0001").get("/api/admin/users").status_code == 403
    assert client("MGR00001").get("/api/admin/stats").status_code == 403
    assert TestClient(app).get("/api/admin/audit").status_code == 401


def test_admin_assigns_roles_only():
    adm = client("ADMN0001")
    users = lambda: {u["cuid"]: u for u in adm.get("/api/admin/users").json()}
    # « Demandeur » ne s'attribue pas : c'est le rôle par défaut
    assert adm.post("/api/admin/users", json={"cuid": "mgr0002", "role": "demandeur"}).status_code == 422
    r = adm.post("/api/admin/users", json={"cuid": "mgr0002", "role": "manager"})
    assert r.status_code == 200
    u, retires = r.json()["user"], r.json()["retires"]
    assert u["cuid"] == "MGR0002" and u["en_attente"] is True and "password_hash" not in u
    assert users()["MGR0002"]["role"] == "manager"
    # Aucun mot de passe ni identité saisis par l'admin (champs refusés)
    assert adm.post("/api/admin/users", json={"cuid": "x3x", "role": "admin", "password": "x"}).status_code == 422
    assert adm.put(f"/api/admin/users/{u['id']}", json={"role": "admin", "email": "a@b.bf"}).status_code == 422
    # Retirer un rôle = remettre demandeur
    assert adm.put(f"/api/admin/users/{u['id']}", json={"role": "admin"}).json()["user"]["role"] == "admin"
    assert adm.put(f"/api/admin/users/{u['id']}", json={"role": "demandeur"}).json()["user"]["role"] == "demandeur"
    # Plus aucune gestion de mot de passe dans l'application
    assert adm.post(f"/api/admin/users/{u['id']}/reset-password").status_code in (404, 405)
    assert client("DEMD0001").post("/api/auth/password", json={}).status_code in (404, 405)


def test_dev_fake_directory():
    """Mode local (dev) : tout CUID se connecte avec SEED_PASSWORD, validateur s'il est enregistré, sinon demandeur."""
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"cuid": "inco9999", "password": PWD})
    assert r.status_code == 200 and r.json()["role"] == "demandeur"
    assert TestClient(app).post("/api/auth/login", json={"cuid": "inco9998", "password": "faux"}).status_code == 401
    adm = client("ADMN0001")
    r_user = adm.post("/api/admin/users", json={"cuid": "fina0002", "role": "rssi"}).json()["user"]
    assert TestClient(app).post("/api/auth/login", json={"cuid": "FINA0002", "password": PWD}).json()["role"] == "rssi"
    adm.put(f"/api/admin/users/{r_user['id']}", json={"role": "demandeur"})
    assert TestClient(app).post("/api/auth/login", json={"cuid": "FINA0002", "password": PWD}).json()["role"] == "demandeur"


def test_admin_safeguards():
    adm = client("ADMN0001")
    me = adm.get("/api/auth/me").json()
    assert adm.post(f"/api/admin/users/{me['id']}/status", json={"is_active": False}).status_code == 400
    assert adm.put(f"/api/admin/users/{me['id']}", json={"role": "demandeur"}).status_code == 400    # son propre rôle


def test_directory_login(monkeypatch):
    """Mode annuaire : l'AD authentifie, l'appli attribue le rôle (demandeur par défaut)."""
    from app.config import get_settings
    from app.directory import DirectoryUnavailable, DirectoryUser, ad_authenticate
    from app.routers import auth as auth_router

    assert ad_authenticate("NEWU0001", "") is None               # jamais de bind anonyme
    directory = {
        "NEWU0001": DirectoryUser("NEWU0001", "Zida", "Rama", "rama.zida@fluxapp.bf", "+226 70 99 88 77", "DSI"),
        "VAL0002": DirectoryUser("VAL0002", "Kone", "Ines", "ines.kone@fluxapp.bf", "+226 70 12 12 12", "RSSI"),
    }

    def fake_ad(cuid, password):
        if password == "panne":
            raise DirectoryUnavailable("timeout")
        return directory.get(cuid) if password == "ad-ok" else None

    monkeypatch.setattr(auth_router, "ad_authenticate", fake_ad)
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_mode", "ldap")
    monkeypatch.setattr(settings, "local_admin_cuid", "ADMN0001")
    login = lambda c, cuid, pwd: c.post("/api/auth/login", json={"cuid": cuid, "password": pwd})

    new = TestClient(app)
    r = login(new, "newu0001", "ad-ok")
    assert r.status_code == 200 and r.json()["role"] == "demandeur" and r.json()["nom"] == "Zida"
    assert login(TestClient(app), "NEWU0001", "faux").status_code == 401
    assert login(TestClient(app), "NEWU0001", "panne").status_code == 503

    adm = client("ADMN0001")
    adm.post("/api/admin/users", json={"cuid": "VAL0002", "role": "admin"})       # rôle attribué avant la connexion AD
    v = login(TestClient(app), "VAL0002", "ad-ok").json()
    assert v["role"] == "admin" and v["email"] == "ines.kone@fluxapp.bf"

    assert login(TestClient(app), "DEMD0001", PWD).status_code == 401      # mot de passe local refusé
    assert login(TestClient(app), "MGR00001", PWD).status_code == 200      # validateur hors AD autorisé en local

    # Resynchronisation automatique si le hash en base etait perime mais SEED_PASSWORD correspond
    with SessionLocal() as db_session:
        mgr = db_session.scalar(select(User).where(User.cuid == "MGR00001"))
        mgr.password_hash = "argon2id$v=19$m=65536,t=3,p=4$badhash$badhash"
        db_session.commit()
    assert login(TestClient(app), "MGR00001", PWD).status_code == 200      # synchronise et accepte

    assert login(TestClient(app), "ADMN0001", PWD).status_code == 200      # compte de secours

    uid = next(u["id"] for u in adm.get("/api/admin/users").json() if u["cuid"] == "NEWU0001")
    adm.post(f"/api/admin/users/{uid}/status", json={"is_active": False})
    assert new.get("/api/auth/me").status_code == 401               # session coupée
    assert login(TestClient(app), "NEWU0001", "ad-ok").status_code == 401  # bloqué dans l'appli malgré l'AD

    rows = adm.get("/api/admin/audit", params={"categorie": "connexions", "q": "ADMN0001"}).json()
    assert any('"secours"' in (r["details"] or "") for r in rows)


def test_trusted_proxy_ip(monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    c = TestClient(app)
    c.post("/api/auth/login", json={"cuid": "DEMD0001", "password": "faux"}, headers={"X-Forwarded-For": "10.9.9.9"})
    monkeypatch.setattr(settings, "trusted_proxies", ["testclient"])
    c.post("/api/auth/login", json={"cuid": "DEMD0001", "password": "faux"}, headers={"X-Forwarded-For": "10.1.2.3"})
    rows = client("ADMN0001").get("/api/admin/audit", params={"categorie": "connexions", "limit": 5}).json()
    ips = [r["ip"] for r in rows]
    assert "10.1.2.3" in ips and "10.9.9.9" not in ips            # en-tête ignoré hors proxy de confiance
    assert all("poste" in (r["details"] or "") for r in rows if r["action"] == "LOGIN_FAILED")


def test_admin_referentials():
    adm = client("ADMN0001")
    zid = adm.post("/api/admin/referentiels/zones", json={"libelle": "DMZ"}).json()["id"]
    assert adm.post("/api/admin/referentiels/zones", json={"libelle": "dmz"}).status_code == 409
    assert adm.put(f"/api/admin/referentiels/zones/{zid}", json={"libelle": "DMZ Internet"}).status_code == 200
    assert adm.delete(f"/api/admin/referentiels/zones/{zid}").status_code == 204
    assert adm.post("/api/admin/referentiels/inconnue", json={"libelle": "X1"}).status_code == 404

    lists = adm.get("/api/admin/referentiels").json()
    ha = next(t for t in lists["flux-types"] if t["libelle"] == "HA")
    assert ha["usage"] > 0                                                                       # demandes existantes
    assert adm.delete(f"/api/admin/referentiels/flux-types/{ha['id']}").status_code == 409
    seul_pays = lists["pays"][0]
    assert adm.delete(f"/api/admin/referentiels/pays/{seul_pays['id']}").status_code == 409     # dernière valeur


def test_admin_stats_and_audit():
    adm = client("ADMN0001")
    st = adm.get("/api/admin/stats").json()
    assert st["total"] == sum(st["par_statut"].values()) and st["total"] > 0
    rows = adm.get("/api/admin/audit", params={"categorie": "administration"}).json()
    assert rows and all(r["action"].startswith(("USER_", "REFERENTIAL_", "FLUX_TYPE_", "DIRECTION_")) for r in rows)
    page2 = adm.get("/api/admin/audit", params={"before_id": rows[-1]["id"], "limit": 5}).json()
    assert all(r["id"] < rows[-1]["id"] for r in page2)
    assert adm.get("/api/admin/audit", params={"categorie": "x"}).status_code == 422


def test_access_type_computed_from_zones():
    c = client("DEMD0001")
    line = c.post("/api/requests/preview", json=payload()).json()["lines"][0]
    assert line["type_acces"] == "Zone1 - Zone2"                       # calculé par le serveur
    forged = payload()
    forged["lines"][0]["type_acces"] = "Prod - Prod"                   # le client ne peut pas l'imposer
    assert c.post("/api/requests/preview", json=forged).status_code == 422
    created = c.post("/api/requests", json=payload()).json()
    assert created["lines"][0]["type_acces"] == "Zone1 - Zone2"
    assert "types_acces" not in c.get("/api/referentiels").json()


def test_validator_stats():
    assert client("DEMD0001").get("/api/requests/validator-stats").status_code == 403
    st = client("MGR00001").get("/api/requests/validator-stats").json()
    assert set(st) == {"a_traiter", "en_retard", "validees_mois", "refusees_mois"}
    assert st["validees_mois"] >= 1 and st["refusees_mois"] >= 1      # décisions des tests précédents
