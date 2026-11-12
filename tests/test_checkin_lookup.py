from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ConferenceRegistration, Invitation
from app.services.qr import build_payload
from tests.test_saas_lot2 import _activate, _event, _invite
from tests.test_conference_badge_flow import generate_sample_photo
from tests.test_saas_lot2 import _conference


def test_lookup_finds_public_and_manual_conference_guests_by_identity_and_stays_event_scoped(make_org):
    admin, _ = make_org()
    event = _conference(admin)
    other_event = _conference(admin)
    _activate(admin, event["id"])
    _activate(admin, other_event["id"])

    public = TestClient(app).post(
        f"/api/public/conferences/{event['registration_token']}/register",
        json={"first_name": "Amina", "last_name": "Kabila", "email": "amina.kabila@example.test", "phone": "+243 812 345 678", "photo_data": generate_sample_photo()},
    )
    assert public.status_code == 201, public.text
    public_id = public.json()["registration"]["id"]
    public_reference = public.json()["registration"]["badge_reference"]
    assert UUID(public_reference).version == 4

    manual = admin.post(
        f"/admin/api/events/{event['id']}/registrations/manual",
        json={"first_name": "Jean", "last_name": "Mbala", "email": "jean.mbala@example.test", "phone": "+243 899 123 456", "profession": "Médecin", "category": "vip"},
    )
    assert manual.status_code == 201, manual.text
    manual_id = manual.json()["id"]
    manual_reference = manual.json()["badge_reference"]
    assert UUID(manual_reference).version == 4 and manual_reference != public_reference

    foreign = TestClient(app).post(
        f"/api/public/conferences/{other_event['registration_token']}/register",
        json={"first_name": "Amina", "last_name": "Kabila", "email": "amina.other@example.test", "phone": "+243 811 000 000", "photo_data": generate_sample_photo()},
    )
    assert foreign.status_code == 201, foreign.text

    def search(q):
        response = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": q})
        assert response.status_code == 200, response.text
        return response.json()

    assert search("Kabila")[0]["id"] == public_id
    assert search("Amina Kabila")[0]["id"] == public_id
    assert search("amina.kabila")[0]["id"] == public_id
    assert search("812 345")[0]["id"] == public_id
    assert search("Mbala")[0]["id"] == manual_id
    assert search("jean.mbala")[0]["is_manual"] is True
    assert search(manual_reference)[0]["reference"] == manual_reference
    assert search("+243 899")[0]["id"] == manual_id
    assert search("absent@example.test") == []
    assert all(row["id"] != foreign.json()["registration"]["id"] for row in search("Amina"))


def test_conference_guest_directory_pdf_uses_the_existing_admin_export(make_org):
    admin, _ = make_org()
    event = _conference(admin)
    created = admin.post(
        f"/admin/api/events/{event['id']}/registrations/manual",
        json={"first_name": "PDF", "last_name": "Guest", "category": "participant"},
    )
    assert created.status_code == 201, created.text

    response = admin.get(f"/admin/api/events/{event['id']}/participants.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")


def test_manual_guest_badge_is_server_verified_and_concurrent_scans_check_in_once(make_org):
    admin, info = make_org()
    event = _conference(admin)
    _activate(admin, event["id"])
    created = admin.post(
        f"/admin/api/events/{event['id']}/registrations/manual",
        json={"first_name": "Invité", "last_name": "Terrain", "category": "staff"},
    )
    assert created.status_code == 201, created.text

    with SessionLocal() as db:
        reg = db.query(ConferenceRegistration).filter_by(id=created.json()["id"]).one()
        badge_token = reg.badge_token
        badge_reference = reg.badge_reference
        assert UUID(badge_reference).version == 4
    token = TestClient(app).post("/api/auth/token", json={"username": info["username"], "password": info["password"]}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    def scan(args):
        badge, key = args
        payload = {"badge_reference": badge} if len(badge) == 36 and badge.count("-") == 4 else {"badge_token": badge}
        return TestClient(app).post(
            f"/checkin/api/conferences/{event['id']}/scan",
            json={**payload, "idempotency_key": key},
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(scan, [(badge_reference, "parallel-scan-one"), (badge_reference, "parallel-scan-two")]))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert {r.json()["status"] for r in responses} == {"checked_in", "already_checked_in"}

    invalid = scan(("unrecognized-badge-token", "parallel-scan-invalid"))
    assert invalid.status_code == 404

    legacy = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_token": badge_token, "idempotency_key": "legacy-badge-scan"})
    assert legacy.status_code == 200 and legacy.json()["status"] == "already_checked_in"
    malformed = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_token": f"CONF:{event['id']}:bad", "idempotency_key": "bad-badge-format"})
    assert malformed.status_code == 422
    malformed_uuid = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_token": f"CONF:{event['id']}:550e8400-e29b-11d4-a716-446655440000", "idempotency_key": "bad-badge-version"})
    assert malformed_uuid.status_code == 422
    unknown = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_token": f"CONF:{event['id']}:550e8400-e29b-41d4-a716-446655440000", "idempotency_key": "unknown-badge-uuid"})
    assert unknown.status_code == 404
    ambiguous = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_reference": badge_reference, "badge_token": badge_token, "idempotency_key": "ambiguous-badge-identifiers"})
    assert ambiguous.status_code == 422
    other_event = _conference(admin)
    _activate(admin, other_event["id"])
    foreign = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_token": f"CONF:{other_event['id']}:{badge_reference}", "idempotency_key": "foreign-event-badge"})
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "Badge ou participant introuvable pour cette conférence."
    foreign_lookup = admin.get(
        f"/checkin/api/events/{event['id']}/lookup",
        params={"q": f"token:CONF:{other_event['id']}:{badge_reference}"},
    )
    unknown_lookup = admin.get(
        f"/checkin/api/events/{event['id']}/lookup",
        params={"q": "token:550e8400-e29b-41d4-a716-446655440000"},
    )
    assert foreign_lookup.status_code == unknown_lookup.status_code == 200
    assert foreign_lookup.json() == unknown_lookup.json() == []
    foreign_reference = admin.post(f"/checkin/api/conferences/{other_event['id']}/scan", json={"badge_reference": badge_reference, "idempotency_key": "foreign-event-reference"})
    assert foreign_reference.status_code == 404

    with SessionLocal() as db:
        db.query(ConferenceRegistration).filter_by(id=created.json()["id"]).update({"status": "cancelled"})
        db.commit()
    revoked = admin.post(f"/checkin/api/conferences/{event['id']}/scan", json={"badge_token": f"CONF:{event['id']}:{badge_reference}", "idempotency_key": "cancelled-badge"})
    assert revoked.status_code == 403


def test_invitation_badge_uuid_is_encoded_and_resolved_by_scan_lookup(make_org):
    admin, _ = make_org()
    event = _event(admin)
    _activate(admin, event["id"])
    created = _invite(admin, event["id"], "UUID invité", quota=1)
    reference = created["reference"]
    assert UUID(reference).version == 4

    with SessionLocal() as db:
        invitation = db.get(Invitation, created["id"])
        assert invitation.badge_reference == reference
        payload = build_payload(event["id"], invitation.badge_reference)

    from app.services.qr import parse_payload
    payload_event, decoded_reference = parse_payload(payload)
    assert payload == f"BADGE:{reference}"
    assert payload_event is None and decoded_reference == reference

    found = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": f"token:{payload}"})
    assert found.status_code == 200 and found.json()[0]["reference"] == reference
    accepted = admin.post(f"/checkin/api/events/{event['id']}/entry", json={"invitation_id": created["id"], "quantity": 1, "idempotency_key": "uuid-entry-test"})
    assert accepted.status_code == 200 and accepted.json()["reference"] == reference
    malformed = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": "token:BADGE:550e8400-e29b-11d4-a716-446655440000"})
    assert malformed.status_code == 422
    unknown = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": f"token:{build_payload(event['id'], '550e8400-e29b-41d4-a716-446655440000')}"})
    assert unknown.status_code == 200 and unknown.json() == []


def test_invitation_qr_lookup_scopes_event_and_exposes_revocation(make_org):
    admin, _ = make_org()
    event = _event(admin)
    other_event = _event(admin)
    invitation = _invite(admin, event["id"], "QR Participant", quota=1)
    other_invitation = _invite(admin, other_event["id"], "Autre Événement", quota=1)
    _activate(admin, event["id"])
    _activate(admin, other_event["id"])

    with SessionLocal() as db:
        token = db.get(Invitation, invitation["id"]).token
        other_token = db.get(Invitation, other_invitation["id"]).token

    valid = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": f"token:IA1.{event['id']}.{token}"})
    assert valid.status_code == 200 and valid.json()[0]["id"] == invitation["id"]
    assert admin.post(f"/checkin/api/events/{event['id']}/entry", json={"invitation_id": invitation["id"], "idempotency_key": "qr-entry-first"}).status_code == 200
    duplicate = admin.post(f"/checkin/api/events/{event['id']}/entry", json={"invitation_id": invitation["id"], "idempotency_key": "qr-entry-second"})
    assert duplicate.status_code == 409
    assert admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": "token:invalid-token-which-is-long-enough"}).json() == []
    foreign = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": f"token:IA1.{other_event['id']}.{other_token}"})
    assert foreign.status_code == 200 and foreign.json() == []

    revoked = admin.post(f"/admin/api/events/{event['id']}/invitations/{invitation['id']}/revoke", json={})
    assert revoked.status_code == 200
    scanned = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": f"token:IA1.{event['id']}.{token}"})
    assert scanned.status_code == 200 and scanned.json()[0]["status"] == "revoked"


def test_idempotent_entry_replay_survives_event_closure(make_org):
    admin, _ = make_org()
    event = _event(admin)
    invitation = _invite(admin, event["id"], "Rejeu QR", quota=1)
    _activate(admin, event["id"])
    payload = {"invitation_id": invitation["id"], "idempotency_key": "replay-after-close"}
    first = admin.post(f"/checkin/api/events/{event['id']}/entry", json=payload)
    assert first.status_code == 200
    assert admin.patch(f"/admin/api/events/{event['id']}", json={"name": event["name"], "status": "closed"}).status_code == 200
    replay = admin.post(f"/checkin/api/events/{event['id']}/entry", json=payload)
    assert replay.status_code == 200 and replay.json()["already_registered"] is True


def test_unverified_conference_registration_is_visible_but_cannot_check_in(make_org):
    admin, _ = make_org()
    event = _conference(admin)
    _activate(admin, event["id"])
    created = TestClient(app).post(
        f"/api/public/conferences/{event['registration_token']}/register",
        json={"first_name": "En attente", "last_name": "Email", "email": "pending@example.test", "phone": "+243 800 000 000"},
    )
    assert created.status_code == 201
    with SessionLocal() as db:
        registration = db.query(ConferenceRegistration).filter_by(event_id=event["id"], email="pending@example.test").one()
        registration_id, badge_token = registration.id, registration.badge_token

    result = admin.get(f"/checkin/api/events/{event['id']}/lookup", params={"q": "pending@example.test"})
    assert result.status_code == 200 and result.json()[0]["status"] == "pending"
    assert result.json()[0]["id"] == registration_id
    rejected = admin.post(
        f"/checkin/api/conferences/{event['id']}/scan",
        json={"badge_token": badge_token, "idempotency_key": "unverified-badge-scan"},
    )
    assert rejected.status_code == 403
