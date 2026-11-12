import base64
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

from app.models import Notification, PushOutbox, PushSubscription
from app.services.messaging import get_vapid_public_key
from app.services.messaging import notify_user
from app.services.push_worker import process_push_outbox_batch


def _set_vapid(monkeypatch, public_format="der"):
    pair = Vapid()
    pair.generate_keys()
    private = pair.private_key.private_numbers().private_value.to_bytes(32, "big")
    point = pair.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    public = point if public_format == "raw" else pair.public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", base64.urlsafe_b64encode(private).decode().rstrip("="))
    monkeypatch.setenv("VAPID_PUBLIC_KEY", base64.urlsafe_b64encode(public).decode().rstrip("="))
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:tests@example.test")
    return base64.urlsafe_b64encode(point).decode().rstrip("=")


def test_vapid_public_key_normalizes_der_and_raw_formats(monkeypatch):
    expected = _set_vapid(monkeypatch, "der")
    assert get_vapid_public_key() == expected
    _set_vapid(monkeypatch, "raw")
    assert get_vapid_public_key() is not None


def test_vapid_public_key_rejects_missing_or_mismatched_pair(monkeypatch):
    _set_vapid(monkeypatch, "raw")
    monkeypatch.setenv("VAPID_PUBLIC_KEY", base64.urlsafe_b64encode(b"not-a-key").decode().rstrip("="))
    assert get_vapid_public_key() is None
    monkeypatch.delenv("VAPID_PRIVATE_KEY")
    assert get_vapid_public_key() is None


def test_push_public_key_returns_normalized_point(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient

    expected = _set_vapid(monkeypatch, "der")
    response = TestClient(app).get("/api/push/public-key")
    assert response.status_code == 200
    assert response.json() == {"public_key": expected}


def test_push_public_key_fails_closed_for_invalid_configuration(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "invalid")
    response = TestClient(app).get("/api/push/public-key")
    assert response.status_code == 503


def test_push_subscription_is_owned_by_one_account_and_unsubscribe_is_scoped(make_org, db, monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient

    _set_vapid(monkeypatch, "raw")
    admin_a, _ = make_org()
    admin_b, _ = make_org()
    endpoint = "https://push.example.test/subscription-a"
    subscription = {"endpoint": endpoint, "keys": {"p256dh": "A" * 87, "auth": "B" * 22}}

    assert admin_a.post("/api/push/subscribe", json=subscription).status_code == 200
    user_a = admin_a.get("/api/me").json()
    notify_user(user_a["id"], user_a["organization_id"], "Queued", "Before unsubscribe")
    assert admin_b.post("/api/push/subscribe", json=subscription).status_code == 409
    assert admin_b.request("DELETE", "/api/push/subscribe", json={"endpoint": endpoint}).status_code == 200
    row = db.query(PushSubscription).filter_by(endpoint=endpoint).one()
    assert row.user_id == user_a["id"]
    assert db.query(PushOutbox).filter_by(subscription_id=row.id).count() == 1
    assert admin_a.request("DELETE", "/api/push/subscribe", json={"endpoint": endpoint}).status_code == 200
    assert db.query(PushSubscription).filter_by(endpoint=endpoint).count() == 0
    assert db.query(PushOutbox).filter_by(subscription_id=row.id).count() == 0


def test_push_subscription_rejects_malformed_keys(make_org, monkeypatch):
    _set_vapid(monkeypatch, "raw")
    admin, _ = make_org()
    response = admin.post("/api/push/subscribe", json={
        "endpoint": "https://push.example.test/subscription-b",
        "keys": {"p256dh": [], "auth": "short"},
    })
    assert response.status_code == 422


def test_internal_notifications_and_read_state_are_user_scoped(make_org, db):
    admin_a, _ = make_org()
    admin_b, _ = make_org()
    user_a = admin_a.get("/api/me").json()
    row = Notification(organization_id=user_a["organization_id"], user_id=user_a["id"], title="Private test",
                       body="Only for account A", category="test", created_at=datetime.now(timezone.utc))
    db.add(row)
    db.commit()
    notification_id = row.id

    assert [n["id"] for n in admin_a.get("/api/notifications").json()] == [notification_id]
    assert admin_b.get("/api/notifications").json() == []
    assert admin_b.post(f"/api/notifications/{notification_id}/read").status_code == 404
    assert admin_a.post(f"/api/notifications/{notification_id}/read").status_code == 200


def test_push_worker_is_bound_to_application_lifespan():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app):
        worker = app.state.push_outbox_worker
        assert not worker.done()
    assert worker.done()


def _add_push_subscription(db, user_id, endpoint):
    subscription = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh="A" * 87, auth="B" * 22)
    db.add(subscription)
    db.commit()
    return subscription.id


def test_push_notifications_are_queued_then_delivered_by_worker(make_org, db, monkeypatch):
    import pywebpush

    _set_vapid(monkeypatch, "raw")
    admin, _ = make_org()
    user = admin.get("/api/me").json()
    subscription_id = _add_push_subscription(db, user["id"], "https://push.example.test/queued-delivery")
    delivered = []

    def fake_webpush(subscription, payload, **kwargs):
        delivered.append((subscription, json.loads(payload), kwargs))

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    notify_user(user["id"], user["organization_id"], "Nouvelle responsabilité", "Accueil", 17, "task")

    job = db.query(PushOutbox).filter_by(subscription_id=subscription_id).one()
    assert job.status == "pending"
    assert delivered == []  # HTTP request path only persisted the notification and job.

    assert process_push_outbox_batch(limit=1) == 1
    db.expire_all()
    job = db.query(PushOutbox).filter_by(subscription_id=subscription_id).one()
    assert job.status == "sent"
    assert len(delivered) == 1
    assert delivered[0][1] == {"title": "Nouvelle responsabilité", "body": "Accueil", "url": "/event/17"}
    assert delivered[0][2]["timeout"] == 10


def test_push_worker_retries_provider_errors_without_leaking_error_text(make_org, db, monkeypatch):
    import pywebpush

    _set_vapid(monkeypatch, "raw")
    admin, _ = make_org()
    user = admin.get("/api/me").json()
    subscription_id = _add_push_subscription(db, user["id"], "https://push.example.test/retry")

    def temporary_failure(*args, **kwargs):
        error = RuntimeError("private endpoint details")
        error.response = SimpleNamespace(status_code=503)
        raise error

    monkeypatch.setattr(pywebpush, "webpush", temporary_failure)
    notify_user(user["id"], user["organization_id"], "Alerte", "Test", 18)
    assert process_push_outbox_batch(limit=1) == 1
    db.expire_all()
    job = db.query(PushOutbox).filter_by(subscription_id=subscription_id).one()
    assert job.status == "pending"
    assert job.attempts == 1
    assert job.last_error == "provider_http_503"
    assert "private" not in job.last_error


def test_push_worker_removes_expired_provider_subscriptions(make_org, db, monkeypatch):
    import pywebpush

    _set_vapid(monkeypatch, "raw")
    admin, _ = make_org()
    user = admin.get("/api/me").json()
    endpoint = "https://push.example.test/expired"
    subscription_id = _add_push_subscription(db, user["id"], endpoint)

    def expired(*args, **kwargs):
        error = RuntimeError("expired")
        error.response = type("Response", (), {"status_code": 410})()
        raise error

    monkeypatch.setattr(pywebpush, "webpush", expired)
    notify_user(user["id"], user["organization_id"], "Alerte", "Test", 19)
    assert process_push_outbox_batch(limit=1) == 1
    assert db.query(PushSubscription).filter_by(id=subscription_id).count() == 0
    assert db.query(PushOutbox).filter_by(subscription_id=subscription_id).count() == 0
