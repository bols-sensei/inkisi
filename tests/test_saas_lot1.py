"""Lot 1 : la logique SaaS est appliquée par le serveur (et pas seulement présente dans le schéma)."""
import re
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.models import Subscription, Plan, Organization
from tests.conftest import login


def _event(admin, name="Mariage", **extra):
    return admin.post("/admin/api/events", json={"name": name, **extra})


def _activate(admin, event_id, name="Mariage"):
    r = admin.patch(f"/admin/api/events/{event_id}", json={"name": name, "status": "active"})
    assert r.status_code == 200, r.text


# ---------- 1.6 superadmin hors tenant ----------
def test_superadmin_has_no_organization(platform):
    me = platform.get("/api/me").json()
    assert me["role"] == "superadmin" and me["organization_id"] is None


# ---------- 1.5 inscription : e-mail obligatoire, unique, essai limité ----------
def test_register_requires_email_and_is_unique(make_org):
    pub = TestClient(app)
    base = {"name": "Sans mail", "admin_full_name": "X Y", "admin_username": "sansmail", "admin_password": "AdminPassword-123"}
    assert pub.post("/api/organizations/register", json=base).status_code == 422
    _, info = make_org()
    again = {**base, "name": "Autre nom", "admin_username": "autreid", "admin_email": info["email"].upper()}
    assert pub.post("/api/organizations/register", json=again).status_code == 409  # un essai par adresse


def test_unverified_admin_cannot_create_events_then_can(make_org):
    admin, info = make_org(verified=False)
    r = _event(admin)
    assert r.status_code == 403 and "e-mail" in r.json()["detail"]
    token = info["verification_url"].rsplit("/", 1)[1]
    assert TestClient(app).get(f"/verify-account/{token}").status_code == 200          # GET sans effet
    assert _event(admin).status_code == 403
    assert TestClient(app).post(f"/verify-account/{token}").status_code == 200
    assert admin.get("/api/me").json()["email_verified"] is True
    assert _event(admin).status_code in (200, 201)
    assert TestClient(app).post(f"/verify-account/{token}").status_code == 400          # usage unique


def test_trial_quota_is_finite(make_org):
    admin, _ = make_org()
    assert _event(admin, "E1").status_code in (200, 201)
    assert _event(admin, "E2").status_code in (200, 201)
    r = _event(admin, "E3")
    assert r.status_code == 403 and "Quota" in r.json()["detail"]


# ---------- 1.1 effet immédiat : désactivation, rôle, mot de passe ----------
def test_deactivating_user_cuts_existing_session_and_jwt(make_org, make_agent):
    admin, _ = make_org()
    uid, body = make_agent(admin)
    agent = login(body["username"], body["password"])
    jwt = TestClient(app).post("/api/auth/token", json={"username": body["username"], "password": body["password"]}).json()["access_token"]
    assert agent.get("/api/me").status_code == 200
    assert admin.patch(f"/admin/api/users/{uid}", json={"active": False}).status_code == 200
    assert agent.get("/api/me").status_code == 401
    assert TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {jwt}"}).status_code == 401
    assert TestClient(app, follow_redirects=False).post("/login", data={"username": body["username"], "password": body["password"]}).status_code == 401


def test_stale_cookie_does_not_loop_on_home(make_org, make_agent):
    admin, _ = make_org()
    uid, body = make_agent(admin)
    agent = login(body["username"], body["password"])
    admin.patch(f"/admin/api/users/{uid}", json={"active": False})
    r = agent.get("/")
    assert r.status_code == 200 and "Connexion" in r.text  # page de connexion, pas le tableau de bord


def test_role_change_applies_immediately(make_org, make_agent):
    admin, _ = make_org()
    uid, body = make_agent(admin, "supervisor")
    sup = login(body["username"], body["password"])
    assert sup.get("/api/me").json()["role"] == "supervisor"
    admin.patch(f"/admin/api/users/{uid}", json={"role": "agent"})
    assert sup.get("/api/me").status_code == 401  # session révoquée, reconnexion avec le nouveau rôle
    assert login(body["username"], body["password"]).get("/api/me").json()["role"] == "agent"


def test_password_change_revokes_other_sessions_but_keeps_current(make_org):
    admin, info = make_org()
    other = login(info["username"], info["password"])
    r = admin.post("/api/me/password", json={"current_password": info["password"], "new_password": "NewPassword-456"})
    assert r.status_code == 200
    assert admin.get("/api/me").status_code == 200
    assert other.get("/api/me").status_code == 401
    assert admin.post("/api/me/password", json={"current_password": "mauvais-mot-de-passe", "new_password": "AnotherPass-789"}).status_code == 403


# ---------- 1.7 gestion d'équipe par l'admin ----------
def test_admin_manages_team_but_only_own_org(make_org, make_agent):
    a1, _ = make_org(); a2, _ = make_org()
    uid, _body = make_agent(a1)
    assert a2.patch(f"/admin/api/users/{uid}", json={"active": False}).status_code == 404  # isolation entre organisations


def test_last_admin_and_self_protection(make_org):
    admin, info = make_org()
    me = admin.get("/api/me").json()
    assert admin.patch(f"/admin/api/users/{me['id']}", json={"active": False}).status_code == 409
    assert admin.patch(f"/admin/api/users/{me['id']}", json={"role": "agent"}).status_code == 409


def test_password_reset_flow_is_neutral_and_revokes(make_org):
    admin, info = make_org()
    pub = TestClient(app)
    unknown = pub.post("/forgot-password", data={"email": "inconnu@example.com"})
    known = pub.post("/forgot-password", data={"email": info["email"]})
    assert unknown.status_code == known.status_code == 200
    assert "dev_link" not in unknown.text and "reset-password/" not in unknown.text
    link = re.search(r'href="([^"]*/reset-password/[^"]+)"', known.text).group(1)
    token = link.rsplit("/", 1)[1]
    assert pub.post(f"/reset-password/{token}", data={"new_password": "court"}).status_code == 422
    assert pub.post(f"/reset-password/{token}", data={"new_password": "BrandNewPass-1"}).status_code == 200
    assert pub.post(f"/reset-password/{token}", data={"new_password": "BrandNewPass-2"}).status_code == 400  # usage unique
    assert admin.get("/api/me").status_code == 401  # ancienne session révoquée
    assert login(info["username"], "BrandNewPass-1").get("/api/me").status_code == 200


# ---------- 1.2 suspension d'organisation ----------
def test_suspended_org_is_blocked_immediately(make_org, platform):
    admin, info = make_org()
    assert platform.patch(f"/superadmin/api/organizations/{info['org_id']}/status", json={"status": "suspended", "reason": "impayé"}).status_code == 200
    assert admin.get("/api/me").status_code == 403
    assert TestClient(app, follow_redirects=False).post("/login", data={"username": info["username"], "password": info["password"]}).status_code == 403
    platform.patch(f"/superadmin/api/organizations/{info['org_id']}/status", json={"status": "active"})
    assert admin.get("/api/me").status_code == 200


# ---------- 1.3 abonnement échu : grâce puis lecture seule ----------
def _expire(db, org_id, days_ago):
    sub = db.query(Subscription).filter_by(organization_id=org_id).order_by(Subscription.id.desc()).first()
    sub.starts_at = datetime.now(timezone.utc) - timedelta(days=days_ago + 20)
    sub.ends_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db.commit()


def test_expired_subscription_grace_then_readonly(make_org, make_agent, db):
    admin, info = make_org()
    ev = _event(admin).json()["id"]
    uid, body = make_agent(admin)
    _expire(db, info["org_id"], days_ago=2)                       # grâce (7 jours par défaut)
    assert _event(admin, "Nouveau").status_code == 403            # jamais de nouvel événement échu
    assert admin.post("/admin/api/users", json={"username": "grace1", "full_name": "G", "password": "UserPassword-123"}).status_code == 200
    _expire(db, info["org_id"], days_ago=30)                      # lecture seule
    r = admin.post("/admin/api/users", json={"username": "ro1", "full_name": "R", "password": "UserPassword-123"})
    assert r.status_code == 403 and "lecture seule" in r.json()["detail"]
    assert admin.patch(f"/admin/api/events/{ev}", json={"name": "Renommé"}).status_code == 403
    assert admin.get(f"/admin/api/events/{ev}").status_code == 200                      # consultation OK
    assert admin.patch(f"/admin/api/users/{uid}", json={"active": False}).status_code == 200  # retirer un accès reste possible
    sub = admin.get("/admin/api/subscription").json()
    assert sub["state"] == "readonly"


def test_active_event_stays_operable_in_readonly(make_org, make_agent, db):
    admin, info = make_org()
    ev = _event(admin).json()["id"]
    inv = admin.post(f"/admin/api/events/{ev}/invitations", json={"guest_name": "Invité", "quota": 2}).json()
    _activate(admin, ev)
    _expire(db, info["org_id"], days_ago=30)
    r = admin.post(f"/checkin/api/events/{ev}/entry", json={"invitation_id": inv["id"], "quantity": 1})
    assert r.status_code == 200, r.text


# ---------- 1.4 fonctionnalités de formule ----------
def test_plan_feature_flag_is_enforced(make_org, platform, db):
    admin, info = make_org()
    plan = db.query(Plan).filter_by(code="trial").first()
    plan.advanced_features = False
    db.commit()
    try:
        r = _event(admin, "Conf", event_type="conference")
        assert r.status_code == 403 and "formule" in r.json()["detail"]
        assert _event(admin, "Mariage").status_code in (200, 201)
    finally:
        plan.advanced_features = True
        db.commit()


# ---------- 1.5 (suite) statut d'événement et révocation ----------
def test_entry_requires_active_event(make_org):
    admin, _ = make_org()
    ev = _event(admin).json()["id"]
    inv = admin.post(f"/admin/api/events/{ev}/invitations", json={"guest_name": "Invité", "quota": 1}).json()
    r = admin.post(f"/checkin/api/events/{ev}/entry", json={"invitation_id": inv["id"]})
    assert r.status_code == 409 and "activez" in r.json()["detail"].lower()
    _activate(admin, ev)
    assert admin.post(f"/checkin/api/events/{ev}/entry", json={"invitation_id": inv["id"]}).status_code == 200


def test_revoke_restore_and_regenerate_token(make_org):
    admin, _ = make_org()
    ev = _event(admin).json()["id"]
    inv = admin.post(f"/admin/api/events/{ev}/invitations", json={"guest_name": "Invité", "quota": 2}).json()
    _activate(admin, ev)
    detail = admin.get(f"/admin/api/events/{ev}").json()
    iid = detail["invitations"][0]["id"]
    assert admin.post(f"/admin/api/events/{ev}/invitations/{iid}/revoke", json={"reason": "QR diffusé"}).status_code == 200
    assert admin.post(f"/checkin/api/events/{ev}/entry", json={"invitation_id": iid}).status_code == 409
    assert admin.post(f"/admin/api/events/{ev}/invitations/{iid}/restore").status_code == 200
    out = admin.post(f"/admin/api/events/{ev}/invitations/{iid}/regenerate-token", json={}).json()
    assert out["qr_payload"].startswith("BADGE:")
    new_reference = out["qr_payload"].removeprefix("BADGE:")
    assert admin.get(f"/checkin/api/events/{ev}/lookup", params={"q": f"token:{new_reference}"}).json()
    assert not admin.get(f"/checkin/api/events/{ev}/lookup", params={"q": "token:ancien-jeton-invalide"}).json()


def test_cross_tenant_event_is_hidden(make_org):
    a1, _ = make_org(); a2, _ = make_org()
    ev = _event(a1).json()["id"]
    assert a2.get(f"/admin/api/events/{ev}").status_code == 404
    assert a2.post(f"/admin/api/events/{ev}/invitations", json={"guest_name": "X", "quota": 1}).status_code == 404
