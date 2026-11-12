import io
import base64
from datetime import datetime, timedelta, timezone
import PIL.Image
import PIL.ImageDraw
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Organization, Plan, Subscription, Event, User, EventAssignment, ConferenceRegistration, ConferenceCheckin
from app.security import hash_password, create_access_token


def generate_sample_photo():
    img = PIL.Image.new('RGB', (300, 300), color=(11, 93, 75))
    d = PIL.ImageDraw.Draw(img)
    d.rectangle([20, 20, 280, 280], fill=(220, 239, 231))
    d.ellipse([100, 60, 200, 160], fill=(11, 93, 75))
    d.ellipse([60, 170, 240, 310], fill=(11, 93, 75))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def test_simplified_conference_registration_and_badge_flow():
    db = SessionLocal()
    # 1. Création de l'organisation et abonnement actif
    plan = db.query(Plan).filter_by(code='pro').first()
    if not plan:
        plan = Plan(code='pro', name='Formule Pro', event_limit=10, advanced_features=True, active=True)
        db.add(plan); db.flush()

    org = Organization(name="Tech Conf Organization", slug="tech-conf-org-test", status="active")
    db.add(org); db.flush()

    sub = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status='active',
        ends_at=datetime.now(timezone.utc) + timedelta(days=365)
    )
    admin = User(
        organization_id=org.id,
        username="admin_conf_user",
        email="admin_conf@test.fr",
        full_name="Admin Conf",
        password_hash=hash_password("AdminPassword-123"),
        role="admin",
        active=True
    )
    db.add_all([sub, admin]); db.flush()

    # 2. Création de l'événement conférence
    event = Event(
        organization_id=org.id,
        name="Sommet Tech & Événements 2026",
        event_date="2026-11-20 09:30",
        venue="Palais des Congrès, Salle A",
        event_type="conference",
        status="active",
        capacity=100,
        registration_open=True,
        registration_token="conf-simplified-token-123"
    )
    db.add(event); db.flush()
    db.add(EventAssignment(event_id=event.id, user_id=admin.id))
    db.commit()
    event_id = event.id
    reg_token = event.registration_token
    admin_id = admin.id
    org_id = org.id
    db.close()

    client = TestClient(app, base_url="http://testserver")

    # 3. Inscription simplifiée avec photo (sans catégorie, sans blocage email)
    sample_photo = generate_sample_photo()
    payload = {
        "full_name": "Sarah ALAMI",
        "organization_name": "Institut International du Numérique",
        "phone": "+33 6 12 34 56 78",
        "email": "sarah.alami@conference-test.fr",
        "photo_data": sample_photo
    }

    r = client.post(f"/api/public/conferences/{reg_token}/register", json=payload)
    assert r.status_code == 201, r.text
    res = r.json()

    assert res["status"] == "accepted"
    assert res["email_verified"] is True
    assert "badge_url" in res and res["badge_url"] is not None
    public_token = res["public_token"]
    badge_token = res["registration"]["badge_token"]
    badge_reference = res["registration"]["badge_reference"]
    from uuid import UUID
    assert UUID(badge_reference).version == 4
    reg_id = res["registration"]["id"]

    assert res["registration"]["full_name"] == "Sarah ALAMI"
    assert res["registration"]["event_name"] == "Sommet Tech & Événements 2026"
    assert res["registration"]["has_photo"] is True
    assert res["registration"]["photo_data"].startswith("data:image/jpeg;base64,")

    # 4. Vérification de l'endpoint d'affichage direct du QR code image
    r_qr = client.get(f"/api/public/conferences/badge-qr/{public_token}.png")
    assert r_qr.status_code == 200
    assert r_qr.headers["content-type"] == "image/png"
    assert len(r_qr.content) > 100

    # 5. Téléchargement du Badge officiel PNG (Exigence 1)
    r_badge = client.get(res["badge_url"])
    assert r_badge.status_code == 200
    assert r_badge.headers["content-type"] == "image/png"
    assert f'filename="badge_{reg_id}.png"' in r_badge.headers["content-disposition"]
    assert r_badge.content.startswith(b"\x89PNG")
    assert len(r_badge.content) > 5000  # Contient le design graphique, la photo, le titre, le nom, le QR code

    # 6. Vérification des doublons : refus d'une seconde inscription avec le même e-mail (Exigence 5)
    r_dup = client.post(f"/api/public/conferences/{reg_token}/register", json=payload)
    assert r_dup.status_code == 409, r_dup.text
    assert "inscrite" in r_dup.json()["detail"]

    # Deuxième inscription avec un e-mail distinct et toutes les informations obligatoires
    payload_valid2 = {
        "first_name": "Marc",
        "last_name": "LEGRAND",
        "organization_name": "Solutions Métier",
        "profession": "Consultant Senior",
        "phone": "+33 6 98 76 54 32",
        "email": "marc.legrand@conference-test.fr",
        "photo_data": sample_photo
    }
    r2 = client.post(f"/api/public/conferences/{reg_token}/register", json=payload_valid2)
    assert r2.status_code == 201, r2.text
    res2 = r2.json()
    assert res2["status"] == "accepted"
    assert res2["badge_url"] is not None

    r2_badge = client.get(res2["badge_url"])
    assert r2_badge.status_code == 200
    assert r2_badge.headers["content-type"] == "image/png"
    assert r2_badge.content.startswith(b"\x89PNG")

    # Inscription sans e-mail : refusée car obligatoire (Exigence 5)
    r_no_email = client.post(f"/api/public/conferences/{reg_token}/register", json={
        "full_name": "Sans Email", "phone": "+33 6 00 00 00 00", "email": ""
    })
    assert r_no_email.status_code == 422

    # 7. Contrôle d'accès terrain : scan du badge par l'administrateur / agent
    token_admin, _ = create_access_token({
        "id": admin_id,
        "username": "admin_conf_user",
        "full_name": "Admin Conf",
        "role": "admin",
        "organization_id": org_id
    })
    auth_headers = {"Authorization": f"Bearer {token_admin}"}

    scan_payload = {
        "badge_reference": badge_reference,
        "idempotency_key": "scan-key-test-sarah-01"
    }
    r_scan = client.post(f"/checkin/api/conferences/{event_id}/scan", json=scan_payload, headers=auth_headers)
    assert r_scan.status_code == 200, r_scan.text
    scan_result = r_scan.json()
    assert scan_result["status"] == "checked_in"
    assert scan_result["name"] == "Sarah ALAMI"

    # Deuxième tentative de scan (rejeu immédiat) : détection de double passage
    r_scan_dup = client.post(
        f"/checkin/api/conferences/{event_id}/scan",
        json={"badge_reference": badge_reference, "idempotency_key": "scan-key-test-sarah-02"},
        headers=auth_headers
    )
    assert r_scan_dup.status_code == 200
    assert r_scan_dup.json()["status"] == "already_checked_in"
    r_legacy_qr = client.post(
        f"/checkin/api/conferences/{event_id}/scan",
        json={"badge_token": badge_token, "idempotency_key": "scan-key-test-sarah-legacy"},
        headers=auth_headers
    )
    assert r_legacy_qr.status_code == 200 and r_legacy_qr.json()["status"] == "already_checked_in"

    # 8. Test d'affichage des pages HTML publiques
    # Page de formulaire public : vérifie que la catégorie a disparu et que le picker photo est présent
    r_page_form = client.get(f"/conference/{reg_token}")
    assert r_page_form.status_code == 200
    html_form = r_page_form.text
    assert "name=\"category\"" not in html_form
    assert "id=\"photoInput\"" in html_form
    assert "id=\"badgeResult\"" in html_form

    # Page de gestion / consultation du badge autonome
    r_page_badge = client.get(f"/conference/registration/{public_token}")
    assert r_page_badge.status_code == 200
    html_badge = r_page_badge.text
    assert "Sarah ALAMI" in html_badge
    assert f"/api/public/conferences/badge/{public_token}" in html_badge
    assert f"/api/public/conferences/badge-qr/{public_token}.png" in html_badge
