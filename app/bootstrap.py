"""Données de référence et compte plateforme, créés après `alembic upgrade head` (jamais par create_all)."""
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, func
from sqlalchemy.exc import OperationalError, ProgrammingError
from app.database import SessionLocal
from app.models import User, Organization, Plan, Subscription
from app.security import hash_password, verify_password
from app.config import is_production as is_production_cfg

DEFAULT_SLUG = "organisation-principale"


def _production() -> bool:
    return is_production_cfg()


def seed_reference_data() -> None:
    db = SessionLocal()
    try:
        default_org = db.query(Organization).filter_by(slug=DEFAULT_SLUG).first()
        if not default_org:
            default_org = Organization(name="Organisation principale", slug=DEFAULT_SLUG, status="active")
            db.add(default_org); db.flush()
        trial = db.query(Plan).filter_by(code="trial").first()
        if not trial:
            limit = int(os.getenv("TRIAL_EVENT_LIMIT", "2"))
            trial = Plan(code="trial", name="Essai gratuit 14 jours", event_limit=limit, advanced_features=True, active=True)
            db.add(trial); db.flush()
        internal = db.query(Plan).filter_by(code="internal").first()
        if not internal:
            internal = Plan(code="internal", name="Interne (organisation principale)", event_limit=-1, advanced_features=True, active=True)
            db.add(internal); db.flush()
        # L'organisation héritée appartient à l'exploitant : abonnement long, pas un essai de 14 jours.
        if not db.query(Subscription).filter_by(organization_id=default_org.id).first():
            now = datetime.now(timezone.utc)
            db.add(Subscription(organization_id=default_org.id, plan_id=internal.id, status="active", starts_at=now, ends_at=now + timedelta(days=3650)))
        db.query(User).filter(User.organization_id.is_(None), User.role != "superadmin").update({User.organization_id: default_org.id})
        db.execute(text("UPDATE events SET organization_id = :org_id WHERE organization_id IS NULL"), {"org_id": default_org.id})
        db.commit()
    finally:
        db.close()


def bootstrap_admin() -> None:
    admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe-123!")
    if len(admin_password) < 10:
        raise RuntimeError("ADMIN_PASSWORD doit contenir au moins 10 caractères.")
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    email = (os.getenv("ADMIN_EMAIL") or "").strip().lower() or None
    db = SessionLocal()
    try:
        existing = db.query(User).filter(func.lower(User.username) == username.lower()).first()
        if not existing:
            # Le superadmin est du personnel de plateforme : aucune organisation cliente.
            db.add(User(username=username, full_name="Superadministrateur", password_hash=hash_password(admin_password),
                        role="superadmin", active=True, organization_id=None, email=email, email_verified=True))
        else:
            existing.role = "superadmin"; existing.active = True; existing.organization_id = None
            if email and not existing.email: existing.email = email; existing.email_verified = True
            sync = os.getenv("ADMIN_SYNC_PASSWORD", "false" if _production() else "true").lower() == "true"
            if sync and not verify_password(admin_password, existing.password_hash):
                existing.password_hash = hash_password(admin_password)
                existing.token_version = int(existing.token_version or 0) + 1
                print(f"[admin] Mot de passe de « {existing.username} » resynchronisé depuis .env")
        db.commit()
    finally:
        db.close()


def init() -> None:
    try:
        seed_reference_data()
        bootstrap_admin()
    except (OperationalError, ProgrammingError) as exc:
        raise RuntimeError("Base non initialisée : exécutez d’abord `alembic upgrade head`.") from exc
