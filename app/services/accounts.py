"""Comptes : e-mails normalisés, jetons à usage unique (vérification d'adresse, réinitialisation de mot de passe)."""
import re, secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from sqlalchemy.orm import Session
from app.models import User, UserToken

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VERIFY = "verify_email"
RESET = "reset_password"
TTL_HOURS = {VERIFY: 24, RESET: 1}


def normalize_email(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    return v or None


def valid_email(value: str | None) -> bool:
    return bool(value and len(value) <= 254 and EMAIL_RE.fullmatch(value))


def issue_token(db: Session, user: User, purpose: str) -> str:
    """Crée un jeton, invalide les précédents du même type, renvoie la valeur en clair (non stockée)."""
    now = datetime.now(timezone.utc)
    db.query(UserToken).filter_by(user_id=user.id, purpose=purpose, used_at=None).update({"used_at": now})
    raw = secrets.token_urlsafe(40)
    db.add(UserToken(user_id=user.id, purpose=purpose, token_hash=sha256(raw.encode()).hexdigest(),
                     expires_at=now + timedelta(hours=TTL_HOURS[purpose])))
    return raw


def peek_token(db: Session, raw: str, purpose: str) -> UserToken | None:
    row = db.query(UserToken).filter_by(token_hash=sha256((raw or "").encode()).hexdigest(), purpose=purpose, used_at=None).first()
    if not row:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    return row if expires > datetime.now(timezone.utc) else None


def consume_token(db: Session, raw: str, purpose: str) -> User | None:
    row = peek_token(db, raw, purpose)
    if not row:
        return None
    row.used_at = datetime.now(timezone.utc)
    return db.query(User).filter_by(id=row.user_id, active=True).first()
