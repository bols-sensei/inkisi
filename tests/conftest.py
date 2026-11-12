"""Environnement de test : base SQLite jetable, tables créées avant l'import de l'application
(main.py amorce la plateforme à l'import), limitation de débit désactivée."""
import os, sys, tempfile
from pathlib import Path

_tmp = Path(tempfile.mktemp(prefix="ia-tests-", suffix=".db", dir=".")).name
os.environ.update({
    "DATABASE_URL": f"sqlite:///./{_tmp}",
    "ENVIRONMENT": "development",
    "RATE_LIMIT_DISABLED": "true",
    "ADMIN_USERNAME": "root",
    "ADMIN_PASSWORD": "RootPassword-123",
    "SECRET_KEY": "test-secret-key",
    "PUBLIC_BASE_URL": "http://testserver",
})
os.environ.pop("SMTP_HOST", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402

_counter = {"n": 0}


def _uid() -> str:
    _counter["n"] += 1
    return f"{_counter['n']:04d}"


def login(username: str, password: str) -> TestClient:
    client = TestClient(app, follow_redirects=False)
    r = client.post("/login", data={"username": username, "password": password})
    assert r.status_code == 303, r.text
    return client


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def platform():
    return login("root", "RootPassword-123")


@pytest.fixture()
def make_org():
    """Crée une organisation cliente via l'inscription publique, confirme l'e-mail, renvoie (client admin, infos)."""
    def _make(verified: bool = True):
        n = _uid()
        pub = TestClient(app, follow_redirects=False)
        body = {"name": f"Org {n}", "admin_full_name": f"Admin {n}", "admin_username": f"admin{n}",
                "admin_password": "AdminPassword-123", "admin_email": f"admin{n}@example.com"}
        r = pub.post("/api/organizations/register", json=body)
        assert r.status_code == 201, r.text
        data = r.json()
        if verified:
            token = data["verification_url"].rsplit("/", 1)[1]
            assert pub.post(f"/verify-account/{token}").status_code == 200
        client = login(body["admin_username"], body["admin_password"])
        return client, {"org_id": data["organization"]["id"], "username": body["admin_username"],
                        "password": body["admin_password"], "email": body["admin_email"], "verification_url": data["verification_url"]}
    return _make


@pytest.fixture()
def make_agent():
    def _make(admin: TestClient, role: str = "agent"):
        n = _uid()
        body = {"username": f"user{n}", "full_name": f"User {n}", "password": "UserPassword-123", "role": role}
        r = admin.post("/admin/api/users", json=body)
        assert r.status_code == 200, r.text
        return r.json()["id"], body
    return _make
