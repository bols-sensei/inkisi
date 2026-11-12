"""Matrice des droits par type de compte : superadmin, admin, supervisor, agent, anonyme, autre organisation.

Chaque route est essayée avec chaque rôle :
  - rôle non autorisé  -> 403 (401 si anonyme) ;
  - rôle autorisé      -> jamais 401/403 (404/409/422 possibles selon l'état, ce n'est pas un refus de droits) ;
  - administrateur d'une AUTRE organisation sur une ressource d'une organisation -> 404 (aucune fuite d'existence).
Les routes qui modifient durablement l'état de la plateforme ne sont essayées que pour les rôles refusés (`denied_only`).
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import login, _uid

ROLES = ("superadmin", "admin", "supervisor", "agent")
PWD = "UserPassword-123"


class World:
    pass


def _register(verified=True):
    n = _uid()
    pub = TestClient(app, follow_redirects=False)
    body = {"name": f"Matrice {n}", "admin_full_name": f"Admin {n}", "admin_username": f"mx_admin{n}",
            "admin_password": "AdminPassword-123", "admin_email": f"mx{n}@example.com"}
    r = pub.post("/api/organizations/register", json=body)
    assert r.status_code == 201, r.text
    if verified:
        assert pub.post("/verify-account/" + r.json()["verification_url"].rsplit("/", 1)[1]).status_code == 200
    return login(body["admin_username"], body["admin_password"]), r.json()["organization"]["id"]


def _create_user(admin, role):
    n = _uid()
    r = admin.post("/admin/api/users", json={"username": f"mx_{role}{n}", "full_name": f"{role} {n}", "password": PWD, "role": role})
    assert r.status_code == 200, r.text
    return r.json()["id"], f"mx_{role}{n}"


@pytest.fixture(scope="module")
def world():
    w = World()
    w.platform = login("root", "RootPassword-123")
    assert w.platform.post("/superadmin/api/plans", json={"code": "matrix", "name": "Matrice", "event_limit": -1, "advanced_features": True}).status_code in (200, 201, 409)
    admin, org = _register()
    w.org = org
    ends = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    assert w.platform.put(f"/superadmin/api/organizations/{org}/subscription", json={"plan_code": "matrix", "status": "active", "ends_at": ends}).status_code == 200
    sup_id, sup_name = _create_user(admin, "supervisor")
    agent_id, agent_name = _create_user(admin, "agent")
    w.spare, _ = _create_user(admin, "agent")                     # cible des routes de gestion
    w.ids = {"sup": sup_id, "agent": agent_id}
    w.clients = {"superadmin": w.platform, "admin": admin, "supervisor": login(sup_name, PWD), "agent": login(agent_name, PWD)}
    w.ev = admin.post("/admin/api/events", json={"name": "Mariage matrice"}).json()["id"]
    conf = admin.post("/admin/api/events", json={"name": "Conférence matrice", "event_type": "conference"}).json()
    w.conf, w.conf_token = conf["id"], conf["registration_token"]
    w.ev_free = admin.post("/admin/api/events", json={"name": "Sans affectation"}).json()["id"]
    for ev in (w.ev, w.conf):
        for uid in (sup_id, agent_id):
            assert admin.post(f"/admin/api/events/{ev}/assignments", json={"user_id": uid}).status_code in (200, 201), "affectation"
    assert admin.patch(f"/admin/api/events/{w.ev}", json={"name": "Mariage matrice", "status": "active"}).status_code == 200
    assert admin.patch(f"/admin/api/events/{w.conf}/conference", json={"capacity": 50, "registration_open": True}).status_code == 200
    w.inv = admin.post(f"/admin/api/events/{w.ev}/invitations", json={"guest_name": "Invité", "quota": 3}).json()["id"]
    w.spare_inv = admin.post(f"/admin/api/events/{w.ev}/invitations", json={"guest_name": "Cible", "quota": 3}).json()["id"]
    w.other_admin, _ = _register()                                   # administrateur d'une autre organisation
    w.anon = TestClient(app, follow_redirects=False)
    return w


# (méthode, chemin, corps, rôles autorisés, denied_only)
def _routes(w):
    ev, conf, inv, sp, org = w.ev, w.conf, w.spare_inv, w.spare, w.org
    A = {"admin", "superadmin"}
    ALL4 = set(ROLES)
    T = datetime.now(timezone.utc)
    prog = {"title": "Session test", "starts_at": T.isoformat(), "ends_at": (T + timedelta(hours=1)).isoformat()}
    plan = {"code": "denied", "name": "Refusé", "event_limit": 1}
    org_body = {"name": "Nom refusé", "admin_full_name": "Admin Refusé", "admin_username": "refuse_admin", "admin_password": "AdminPassword-123"}
    sub = {"plan_code": "trial", "status": "active", "ends_at": (T + timedelta(days=5)).isoformat()}
    return [
        # --- administration d'organisation ---
        ("GET", "/admin/api/overview", None, A, False),
        ("GET", "/admin/api/users", None, A, False),
        ("GET", "/admin/api/audit", None, A, False),
        ("GET", "/admin/api/subscription", None, A, False),
        ("POST", "/admin/api/events", {"name": "Refusé"}, A, True),
        ("PATCH", f"/admin/api/events/{ev}", {"name": "Mariage matrice", "status": "active"}, A, False),
        ("PATCH", f"/admin/api/events/{ev}/status", {"status": "active"}, {"admin", "superadmin", "supervisor"}, False),
        ("PATCH", f"/admin/api/events/{ev}/status", {"status": "closed"}, A, True),
        ("GET", f"/admin/api/events/{ev}/designer-pack", None, A, False),
        ("POST", "/admin/api/users", {"username": "refuse_user", "full_name": "Refusé", "password": PWD}, A, True),
        ("PATCH", f"/admin/api/users/{sp}", {"full_name": "Cible"}, A, False),
        ("POST", f"/admin/api/events/{ev}/assignments", {"user_id": sp}, A, False),
        ("DELETE", f"/admin/api/events/{ev}/assignments/{sp}", None, A, False),
        # --- invitations ---
        ("POST", f"/admin/api/events/{ev}/invitations", {"guest_name": "Nouveau", "quota": 1}, A, False),
        ("PATCH", f"/admin/api/events/{ev}/invitations/{inv}", {"guest_name": "Invité", "quota": 3}, A, False),
        ("POST", f"/admin/api/events/{ev}/invitations/{inv}/revoke", {}, A, True),
        ("POST", f"/admin/api/events/{ev}/invitations/{w.spare_inv}/revoke", {}, A, False),
        ("POST", f"/admin/api/events/{ev}/invitations/{w.spare_inv}/restore", None, A, False),
        ("POST", f"/admin/api/events/{ev}/invitations/{w.spare_inv}/regenerate-token", {}, A, False),
        ("GET", f"/admin/api/events/{ev}/invitations.pdf", None, A, False),
        ("GET", f"/admin/api/events/{ev}/invitations/batch-pdf", None, A, False),
        # --- conférence ---
        ("GET", f"/admin/api/events/{conf}/registration-qr.png", None, A, False),
        ("GET", f"/admin/api/events/{conf}/member-badges", None, A, False),
        ("GET", f"/admin/api/events/{conf}/member-badges/preview.png", None, A, False),
        ("GET", f"/admin/api/events/{conf}/member-badge-qr.png", None, A, False),
        ("PUT", f"/admin/api/events/{conf}/member-badges", {"palette": "royal", "categories": ["Presse", "Protocole"], "enabled": True}, A, False),
        ("PATCH", f"/admin/api/events/{conf}/conference", {"capacity": 50, "registration_open": True}, A, False),
        ("POST", f"/admin/api/events/{conf}/registrations/manual", {"full_name": "Manuel Test", "email": "manuel@example.com"}, A, False),
        ("PATCH", f"/admin/api/events/{conf}/registrations/1/details", {"profession": "Développeur"}, A, False),
        ("POST", f"/admin/api/events/{conf}/registrations/1/regenerate-qr", {}, A, False),
        ("GET", f"/admin/api/events/{conf}/registrations", None, A, False),
        ("POST", f"/admin/api/events/{conf}/program", prog, A, False),
        # --- lecture partagée (admin, superviseur, agent affectés) ---
        ("GET", f"/admin/api/events/{ev}", None, ALL4, False),
        ("GET", f"/api/events/{ev}/program", None, ALL4, False),
        ("GET", f"/api/events/{ev}/program.pdf", None, ALL4, False),
        ("GET", f"/api/events/{ev}/tasks", None, ALL4, False),
        ("GET", "/api/notifications", None, ALL4, False),
        # --- contrôle d'accès ---
        ("GET", f"/checkin/api/events/{ev}/lookup?q=a", None, ALL4, False),
        ("POST", f"/checkin/api/events/{ev}/entry", {"invitation_id": inv}, ALL4, False),
        ("POST", "/checkin/api/sync", {"entries": [{"client_id": "matrix-0001", "event_id": ev, "token": "IA1.0.jeton-inconnu"}]}, ALL4, False),
        ("POST", f"/checkin/api/conferences/{conf}/scan", {"badge_token": "x" * 24}, ALL4, False),
        ("POST", f"/checkin/api/events/{ev}/exceptions", {"invitation_id": inv, "reason": "raison suffisante", "decision": "review"}, {"supervisor"}, False),
        # --- espace superviseur ---
        ("GET", "/supervisor/api/events", None, {"agent", "supervisor"}, False),
        ("GET", f"/supervisor/api/events/{ev}/dashboard", None, {"agent", "supervisor"}, False),
        ("GET", f"/supervisor/api/events/{ev}/agents", None, {"agent", "supervisor"}, False),
        ("GET", f"/supervisor/api/events/{ev}/activity", None, {"admin", "superadmin", "supervisor"}, False),
        ("GET", f"/supervisor/api/events/{ev}/exceptions", None, {"admin", "superadmin", "supervisor"}, False),
        ("POST", f"/admin/api/events/{ev}/tasks", {"title": "Tâche test"}, {"admin", "superadmin", "supervisor"}, False),
        # --- console plateforme (superadmin seul) ---
        ("GET", "/superadmin/api/organizations", None, {"superadmin"}, False),
        ("GET", "/superadmin/api/plans", None, {"superadmin"}, False),
        ("GET", "/superadmin/api/stats", None, {"superadmin"}, False),
        ("GET", "/support/api/tickets", None, {"admin", "superadmin"}, False),
        ("GET", "/support/api/tickets/999999", None, {"admin", "superadmin"}, False),
        ("POST", "/support/api/tickets/999999/messages", {"body": "Réponse test"}, {"admin", "superadmin"}, False),
        ("POST", "/support/api/tickets", {"subject": "Refusé", "body": "Message refusé"}, {"admin"}, True),
        ("GET", f"/superadmin/api/organizations/{org}/detail", None, {"superadmin"}, False),
        ("POST", "/superadmin/api/organizations", org_body, {"superadmin"}, True),
        ("POST", "/superadmin/api/plans", plan, {"superadmin"}, True),
        ("PATCH", f"/superadmin/api/organizations/{org}/status", {"status": "suspended"}, {"superadmin"}, True),
        ("PUT", f"/superadmin/api/organizations/{org}/subscription", sub, {"superadmin"}, True),
        ("PATCH", f"/superadmin/api/users/{sp}", {"active": True}, {"superadmin"}, True),
    ]


def _call(client, method, path, body):
    kw = {"json": body} if body is not None else {}
    return client.request(method, path, **kw)


class _Ids:
    ev = conf = inv = spare = spare_inv = org = 1


N_ROUTES = len(_routes(_Ids()))


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("idx", range(N_ROUTES))
def test_role_matrix(world, idx, role):
    routes = _routes(world)
    method, path, body, allowed, denied_only = routes[idx]
    if denied_only and role in allowed:
        return
    r = _call(world.clients[role], method, path, body)
    label = f"{role} {method} {path} -> {r.status_code} {r.text[:160]}"
    if role in allowed:
        if not denied_only:
            assert r.status_code not in (401, 403), label
    else:
        assert r.status_code == 403, label


@pytest.mark.parametrize("idx", range(N_ROUTES))
def test_anonymous_is_always_refused(world, idx):
    routes = _routes(world)
    method, path, body, _allowed, _d = routes[idx]
    r = _call(world.anon, method, path, body)
    assert r.status_code == 401, f"anonyme {method} {path} -> {r.status_code} {r.text[:160]}"


# --- isolation : l'administrateur d'une autre organisation ne voit rien (404, pas 403) ---
ISOLATION = [
    ("GET", "/admin/api/events/{ev}", None),
    ("PATCH", "/admin/api/events/{ev}", {"name": "Piraté", "status": "closed"}),
    ("GET", "/admin/api/events/{ev}/designer-pack", None),
    ("GET", "/admin/api/events/{ev}/invitations.pdf", None),
    ("POST", "/admin/api/events/{ev}/invitations", {"guest_name": "Intrus", "quota": 1}),
    ("POST", "/admin/api/events/{ev}/invitations/{inv}/revoke", {}),
    ("POST", "/admin/api/events/{ev}/assignments", {"user_id": 1}),
    ("GET", "/admin/api/events/{conf}/registrations", None),
    ("PATCH", "/admin/api/events/{conf}/registrations/1/details", {"profession": "Intrus"}),
    ("POST", "/admin/api/events/{conf}/registrations/1/regenerate-qr", {}),
    ("PATCH", "/admin/api/events/{conf}/conference", {"capacity": 1, "registration_open": False}),
    ("GET", "/checkin/api/events/{ev}/lookup?q=a", None),
    ("POST", "/checkin/api/events/{ev}/entry", {"invitation_id": 1}),
    ("GET", "/supervisor/api/events/{ev}/activity", None),
    ("PATCH", "/admin/api/users/{spare}", {"active": False}),
]


@pytest.mark.parametrize("method,path,body", ISOLATION, ids=[f"{m} {p}" for m, p, _ in ISOLATION])
def test_other_organisation_admin_gets_404(world, method, path, body):
    p = path.format(ev=world.ev, conf=world.conf, inv=world.spare_inv, spare=world.spare)
    r = _call(world.other_admin, method, p, body)
    assert r.status_code == 404, f"{method} {p} -> {r.status_code} {r.text[:160]}"


# --- règles propres à chaque rôle ---
def test_event_visibility_depends_on_assignment(world):
    assert world.clients["admin"].get(f"/admin/api/events/{world.ev_free}").status_code == 200
    assert world.clients["superadmin"].get(f"/admin/api/events/{world.ev_free}").status_code == 200
    assert world.clients["supervisor"].get(f"/admin/api/events/{world.ev_free}").status_code == 403
    assert world.clients["agent"].get(f"/admin/api/events/{world.ev_free}").status_code == 403
    mine = {e["id"] for e in world.clients["agent"].get("/supervisor/api/events").json()}
    assert world.ev in mine and world.ev_free not in mine


@pytest.mark.parametrize("role", ROLES)
def test_me_reports_the_right_role_and_organisation(world, role):
    me = world.clients[role].get("/api/me").json()
    assert me["role"] == role
    assert me["organization_id"] is None if role == "superadmin" else me["organization_id"] == world.org


@pytest.mark.parametrize("role", ["admin", "supervisor", "agent"])
def test_deactivated_account_loses_access_immediately(role):
    admin, _org = _register()
    uid, name = _create_user(admin, role)
    c = login(name, PWD)
    assert c.get("/api/me").status_code == 200
    assert admin.patch(f"/admin/api/users/{uid}", json={"active": False}).status_code == 200
    assert c.get("/api/me").status_code == 401


@pytest.mark.parametrize("role", ["admin", "supervisor", "agent"])
def test_suspended_organisation_blocks_every_tenant_role_but_not_platform(role, world):
    admin, org = _register()
    uid, name = _create_user(admin, role)
    c = login(name, PWD)
    assert c.get("/api/me").status_code == 200
    assert world.platform.patch(f"/superadmin/api/organizations/{org}/status", json={"status": "suspended"}).status_code == 200
    assert c.get("/api/me").status_code == 403
    assert TestClient(app, follow_redirects=False).post("/login", data={"username": name, "password": PWD}).status_code == 403
    assert world.platform.get("/api/me").status_code == 200  # le personnel plateforme n'est pas concerné


@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_change_own_password_and_is_logged_out_elsewhere(role):
    if role == "superadmin":
        pytest.skip("le mot de passe du superadmin est géré par ADMIN_PASSWORD (resynchronisé en développement)")
    admin, _org = _register()
    uid, name = (None, admin_name(admin)) if role == "admin" else _create_user(admin, role)
    pwd = "AdminPassword-123" if role == "admin" else PWD
    first, second = login(name, pwd), login(name, pwd)
    assert first.post("/api/me/password", json={"current_password": pwd, "new_password": "ChangedPass-4567"}).status_code == 200
    assert first.get("/api/me").status_code == 200 and second.get("/api/me").status_code == 401


def admin_name(client):
    return client.get("/api/me").json()["username"]


def test_admin_cannot_touch_platform_accounts(world):
    root_id = world.platform.get("/api/me").json()["id"]
    r = world.clients["admin"].patch(f"/admin/api/users/{root_id}", json={"active": False})
    assert r.status_code in (403, 404)
    assert world.platform.get("/api/me").status_code == 200


def test_supervisor_and_agent_cannot_manage_team_or_subscription(world):
    for role in ("supervisor", "agent"):
        c = world.clients[role]
        assert c.post("/admin/api/users", json={"username": f"x{role}", "full_name": "X", "password": PWD, "role": "admin"}).status_code == 403
        assert c.patch(f"/admin/api/users/{world.spare}", json={"role": "admin"}).status_code == 403
        assert c.get("/admin/api/subscription").status_code == 403


# --- participant public (sans compte) ---
def test_public_participant_only_reaches_public_endpoints(world):
    pub = world.anon
    assert pub.get(f"/api/public/conferences/{world.conf_token}").status_code == 200
    assert pub.get(f"/api/public/conferences/{world.conf_token}/program").status_code == 200
    assert pub.get(f"/conference/{world.conf_token}").status_code == 200
    r = pub.post(f"/api/public/conferences/{world.conf_token}/register", json={"full_name": "Participant Public", "email": "public@example.com"})
    assert r.status_code == 201
    for path in (f"/admin/api/events/{world.conf}/registrations", "/api/me", "/admin/api/overview", "/superadmin/api/stats"):
        assert pub.get(path).status_code == 401, path
    assert pub.get("/api/public/conferences/jeton-inexistant").status_code == 404
