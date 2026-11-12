"""Lot 2 : sécurité (CSRF, CSP, exports, débit, fail-closed) et intégrité (idempotence, dates, audit)."""
import io, os, re, subprocess, sys, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.models import EntryRecord, Invitation
from app.services.qr import build_payload
from tests.conftest import login

ROOT = Path(__file__).resolve().parents[1]


def _event(admin, name="Mariage", **extra):
    r = admin.post("/admin/api/events", json={"name": name, **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _activate(admin, event_id, name="Mariage"):
    assert admin.patch(f"/admin/api/events/{event_id}", json={"name": name, "status": "active"}).status_code == 200


def _invite(admin, ev, name="Invité", quota=2):
    r = admin.post(f"/admin/api/events/{ev}/invitations", json={"guest_name": name, "quota": quota})
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------- S4 : échec fermé ----------
def _run_config(env_extra, unset=()):
    env = {k: v for k, v in os.environ.items() if k not in unset}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-c", "import app.config as c; print(c.is_production())"], cwd=ROOT, env=env, capture_output=True, text=True)


def test_environment_defaults_to_production_and_rejects_typos():
    assert _run_config({}, unset=("ENVIRONMENT",)).stdout.strip() == "True"
    assert _run_config({"ENVIRONMENT": "development"}).stdout.strip() == "False"
    bad = _run_config({"ENVIRONMENT": "prod"})
    assert bad.returncode != 0 and "ENVIRONMENT" in bad.stderr


# ---------- S6 : CSP ----------
def test_csp_header_and_no_inline_script():
    r = TestClient(app).get("/")
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp.split("style-src")[0]
    assert "frame-ancestors 'none'" in csp
    assert not re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*type=\"application/json\")[^>]*>", r.text)


# ---------- S5 : CSRF ----------
def test_cross_origin_state_change_is_refused(make_org):
    admin, _ = make_org()
    evil = {"Origin": "https://evil.example"}
    assert admin.post("/admin/api/events", json={"name": "X"}, headers=evil).status_code == 403
    assert admin.post("/admin/api/events", json={"name": "X"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert admin.post("/admin/api/events", json={"name": "X"}, headers={"Origin": "null"}).status_code == 403
    assert admin.post("/logout", headers={"Referer": "https://evil.example/page"}).status_code == 403
    assert admin.post("/admin/api/events", json={"name": "Légitime"}, headers={"Origin": "http://testserver"}).status_code in (200, 201)


def test_bearer_calls_are_not_origin_checked(make_org):
    _, info = make_org()
    tok = TestClient(app).post("/api/auth/token", json={"username": info["username"], "password": info["password"]}).json()["access_token"]
    r = TestClient(app).post("/admin/api/events", json={"name": "API"}, headers={"Authorization": f"Bearer {tok}", "Origin": "https://partner.example"})
    assert r.status_code in (200, 201)


# ---------- S1 / S2 : exports ----------
def test_pdf_and_excel_exports_neutralise_guest_names(make_org):
    from uuid import UUID
    from app.services.exports import qr_png
    from app.services.qr import build_payload, qr_filename
    admin, _ = make_org()
    ev = _event(admin)["id"]
    first = _invite(admin, ev, '<img src="http://127.0.0.1/x.png"/> & <b>Gras', 1)
    _invite(admin, ev, '=HYPERLINK("http://evil.example","clic")', 1)
    assert UUID(first["reference"]).version == 4
    pdf = admin.get(f"/admin/api/events/{ev}/invitations.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    pack = admin.get(f"/admin/api/events/{ev}/designer-pack")
    assert pack.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(pack.content))
    qr_path = qr_filename(ev, first["reference"])
    assert z.read(qr_path) == qr_png(build_payload(ev, first["reference"]))
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(z.read("manifest_invitations.xlsx"))).active
    names = {row[3].value: row[3].data_type for row in ws.iter_rows(min_row=2)}
    assert names['=HYPERLINK("http://evil.example","clic")'] == "s"  # texte, jamais une formule


# ---------- S3 : débit ----------
def test_login_failures_are_limited_per_account(make_org, monkeypatch):
    from app.services.ratelimit import limiter
    _, info = make_org()
    monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
    limiter.hits.clear()
    try:
        c = TestClient(app, follow_redirects=False)
        for _ in range(5):
            assert c.post("/login", data={"username": info["username"], "password": "mauvais"}).status_code == 401
        # Même avec le bon mot de passe : le compte est temporairement verrouillé pour cette IP.
        assert c.post("/login", data={"username": info["username"], "password": info["password"]}).status_code == 429
    finally:
        limiter.hits.clear()


def test_client_ip_trusts_forwarded_header_only_behind_known_proxies(monkeypatch):
    from starlette.requests import Request
    from app.services.ratelimit import client_ip
    scope = {"type": "http", "headers": [(b"x-forwarded-for", b"6.6.6.6, 9.9.9.9")], "client": ("10.0.0.1", 1234)}
    monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)
    assert client_ip(Request(scope)) == "10.0.0.1"          # en-tête usurpable : ignoré
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    assert client_ip(Request(scope)) == "9.9.9.9"           # ajouté par notre proxy
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "2")
    assert client_ip(Request(scope)) == "6.6.6.6"


# ---------- S7 / S8 : inscriptions publiques ----------
def _conference(admin):
    ev = _event(admin, "Conf", event_type="conference")
    assert admin.patch(f"/admin/api/events/{ev['id']}/conference", json={"capacity": 10, "registration_open": True}).status_code == 200
    return ev


def test_public_registration_is_neutral_and_verification_needs_post(make_org):
    admin, _ = make_org()
    conf = _conference(admin)
    pub = TestClient(app)
    body = {"full_name": "Jean Dupont", "email": "jean@example.com"}
    first = pub.post(f"/api/public/conferences/{conf['registration_token']}/register", json=body)
    again = pub.post(f"/api/public/conferences/{conf['registration_token']}/register", json=body)
    assert first.status_code == again.status_code == 201
    assert "already_registered" not in again.json() and again.json()["message"] == first.json()["message"]
    token = again.json()["verification_url"].rsplit("/", 1)[1]            # le dernier lien est le seul valable
    assert pub.get(f"/conference/verify/{token}").status_code == 200       # GET : page de confirmation, rien consommé
    assert pub.get(f"/conference/verify/{token}").status_code == 200
    assert pub.post(f"/conference/verify/{token}").status_code == 200
    assert pub.post(f"/conference/verify/{token}").status_code == 400
    assert pub.post(f"/api/public/conferences/verify/{token}").status_code == 400


# ---------- D3 : idempotence par événement ----------
def test_same_idempotency_key_in_two_organisations(make_org):
    a1, _ = make_org(); a2, _ = make_org()
    keys = {}
    for admin in (a1, a2):
        ev = _event(admin)["id"]; inv = _invite(admin, ev); _activate(admin, ev)
        r = admin.post(f"/checkin/api/events/{ev}/entry", json={"invitation_id": inv["id"], "idempotency_key": "cle-partagee-0001"})
        assert r.status_code == 200, r.text
        keys[ev] = inv["id"]
    assert len(keys) == 2


# ---------- D2 : date réelle d'un scan hors ligne ----------
def test_offline_scan_keeps_real_time_and_user_binding(make_org, db):
    admin, _ = make_org()
    me = admin.get("/api/me").json()
    ev = _event(admin)["id"]; inv = _invite(admin, ev, quota=3); _activate(admin, ev)
    token = db.query(Invitation).filter_by(id=inv["id"]).first().badge_reference
    scanned = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0)
    entry = {"client_id": "offline-0001", "event_id": ev, "token": build_payload(ev, token), "quantity": 1,
             "method": "qr", "occurred_at": scanned.isoformat(), "user_id": me["id"]}
    r = admin.post("/checkin/api/sync", json={"entries": [entry]})
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "synced", r.text
    db.expire_all()
    rec = db.query(EntryRecord).filter_by(event_id=ev, idempotency_key="offline-0001").one()
    created = rec.created_at if rec.created_at.tzinfo else rec.created_at.replace(tzinfo=timezone.utc)
    assert abs((created - scanned).total_seconds()) < 2 and rec.synced_at is not None
    # Date aberrante (futur) : repli sur l'heure de réception, jamais de rejet du passage.
    future = {**entry, "client_id": "offline-0002", "occurred_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()}
    assert admin.post("/checkin/api/sync", json={"entries": [future]}).json()["results"][0]["status"] == "synced"
    # Scanné par un autre compte : différé, resté en file côté appareil.
    other = {**entry, "client_id": "offline-0003", "user_id": me["id"] + 9999}
    assert admin.post("/checkin/api/sync", json={"entries": [other]}).json()["results"][0]["status"] == "deferred"


# ---------- S10 : journal ----------
def test_audit_log_is_scoped_paginated_and_includes_platform_actions(make_org, make_agent, platform):
    a1, info1 = make_org(); a2, _ = make_org()
    uid, _body = make_agent(a1)
    a1.patch(f"/admin/api/users/{uid}", json={"full_name": "Renommé"})
    _event(a1, "Journalisé")
    platform.put(f"/superadmin/api/organizations/{info1['org_id']}/subscription", json={"plan_code": "trial", "status": "active", "ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()})
    out = a1.get("/admin/api/audit").json()
    actions = [i["action"] for i in out["items"]]
    assert "user.updated" in actions and "event.created" in actions and "platform.subscription.set" in actions
    assert all(i["user"]["username"] for i in out["items"])
    assert not any(i["action"] == "user.updated" for i in a2.get("/admin/api/audit").json()["items"])  # isolation
    page1 = a1.get("/admin/api/audit", params={"limit": 1}).json()
    assert len(page1["items"]) == 1 and page1["next_before_id"]
    page2 = a1.get("/admin/api/audit", params={"limit": 1, "before_id": page1["next_before_id"]}).json()
    assert page2["items"][0]["id"] < page1["items"][0]["id"]
    assert a1.get("/admin/api/audit", params={"action": "user."}).json()["items"][0]["action"].startswith("user.")


def test_agent_cannot_read_audit_log(make_org, make_agent):
    admin, _ = make_org()
    _uid, body = make_agent(admin)
    assert login(body["username"], body["password"]).get("/admin/api/audit").status_code == 403
