import re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Organization, Plan, Subscription, User
from app.security import hash_password
from app.services.accounts import normalize_email, valid_email

TRIAL_DAYS = 14


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:190] or "organisation"


def username_taken(db: Session, username: str) -> bool:
    return db.query(User.id).filter(func.lower(User.username) == username.lower()).first() is not None


def create_organization_with_admin(db: Session, *, name: str, username: str, full_name: str, password: str,
                                   email: str | None, email_verified: bool, require_email: bool):
    """Crée organisation + administrateur + essai. Ne fait pas de commit. Renvoie (org, admin, subscription)."""
    name, username, full_name = name.strip(), username.strip(), full_name.strip()
    email = normalize_email(email)
    if require_email and not email:
        raise HTTPException(422, "Une adresse e-mail est obligatoire pour créer une organisation.")
    if email and not valid_email(email):
        raise HTTPException(422, "Adresse e-mail invalide.")
    if db.query(Organization.id).filter(func.lower(Organization.name) == name.lower()).first():
        raise HTTPException(409, "Une organisation portant ce nom existe déjà.")
    if username_taken(db, username):
        raise HTTPException(409, "Cet identifiant utilisateur existe déjà.")
    if email and db.query(User.id).filter(User.email == email).first():
        raise HTTPException(409, "Cette adresse e-mail est déjà associée à un compte.")
    trial_plan = db.query(Plan).filter_by(code="trial", active=True).first()
    if not trial_plan:
        raise HTTPException(503, "Les inscriptions sont temporairement indisponibles.")
    base = slugify(name); slug = base; n = 2
    while db.query(Organization.id).filter_by(slug=slug).first():
        slug = f"{base}-{n}"; n += 1
    org = Organization(name=name, slug=slug, status="active")
    db.add(org); db.flush()
    admin = User(username=username, full_name=full_name, password_hash=hash_password(password), role="admin", active=True,
                 organization_id=org.id, email=email, email_verified=email_verified)
    db.add(admin)
    now = datetime.now(timezone.utc)
    sub = Subscription(organization_id=org.id, plan_id=trial_plan.id, status="trial", starts_at=now, ends_at=now + timedelta(days=TRIAL_DAYS))
    db.add(sub); db.flush()
    return org, admin, sub
