import os
from datetime import datetime, timedelta, timezone
import jwt
try:
    from pwdlib import PasswordHash
    _password_hash = PasswordHash.recommended()
except ImportError:  # fallback Argon2id; keeps installations working if pwdlib is temporarily absent
    from argon2 import PasswordHasher
    class _Argon2Fallback:
        def __init__(self): self.impl = PasswordHasher()
        def hash(self, value): return self.impl.hash(value)
        def verify(self, value, hashed):
            try: return self.impl.verify(hashed, value)
            except Exception: return False
    _password_hash = _Argon2Fallback()
from fastapi import Request, HTTPException
from app.database import SessionLocal

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_SECRET = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY", "dev-only-change-me")

def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Le mot de passe doit contenir au moins 10 caractères.")
    return _password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try: return _password_hash.verify(password, hashed)
    except Exception: return False

def create_access_token(user: dict) -> tuple[str, int]:
    minutes = max(5, int(os.getenv("JWT_EXPIRE_MINUTES", "60")))
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user["id"]), "username": user["username"], "full_name": user["full_name"], "role": user["role"],
               "organization_id": user.get("organization_id"), "tv": int(user.get("token_version") or 0),
               "iat": now, "exp": now + timedelta(minutes=minutes), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), minutes * 60

def _token_claims(token: str) -> dict:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp", "iat"]})
        if data.get("type") != "access": raise ValueError("Invalid token type")
        return {"id": int(data["sub"]), "tv": int(data.get("tv") or 0)}
    except Exception:
        raise HTTPException(status_code=401, detail="Jeton JWT invalide ou expiré", headers={"WWW-Authenticate": "Bearer"})

def _load_account(claims: dict) -> dict:
    """La base fait foi à chaque requête : compte actif, version de jeton, organisation non suspendue.

    Les rôles et l'organisation des cookies/JWT ne sont jamais crus : un compte désactivé, un rôle modifié,
    un mot de passe changé ou une organisation suspendue prennent effet immédiatement.
    """
    from app.models import User, Organization
    db = SessionLocal()
    try:
        stored = db.query(User).filter_by(id=claims["id"]).first()
        if not stored or not stored.active or int(claims.get("tv") or 0) != int(stored.token_version or 0):
            raise HTTPException(status_code=401, detail="Session expirée ou compte désactivé.")
        if stored.role != "superadmin":
            org = db.query(Organization).filter_by(id=stored.organization_id).first() if stored.organization_id else None
            if not org or org.status != "active":
                raise HTTPException(status_code=403, detail="Organisation suspendue. Contactez le support de la plateforme.")
        return {"id": stored.id, "username": stored.username, "full_name": stored.full_name, "role": stored.role,
                "organization_id": stored.organization_id, "email": stored.email,
                "email_verified": bool(stored.email_verified), "token_version": int(stored.token_version or 0)}
    finally:
        db.close()

def current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return _load_account(_token_claims(auth[7:].strip()))
    user_id = request.session.get("user_id")
    if not user_id: raise HTTPException(status_code=401, detail="Connexion requise")
    try:
        user = _load_account({"id": int(user_id), "tv": request.session.get("tv", 0)})
    except HTTPException as exc:
        if exc.status_code == 401: request.session.clear()  # évite une boucle de redirection avec un cookie périmé
        raise
    request.session.update({"organization_id": user["organization_id"], "role": user["role"], "username": user["username"], "full_name": user["full_name"]})
    return user

def optional_user(request: Request):
    """Utilisateur valide ou None (pour les pages HTML) ; efface une session périmée."""
    try: return current_user(request)
    except HTTPException: return None

def login_session(request: Request, user) -> None:
    request.session.clear()
    request.session.update({"user_id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role,
                            "organization_id": user.organization_id, "tv": int(user.token_version or 0)})

def revoke_sessions(user) -> None:
    """Invalide toutes les sessions et tous les JWT déjà émis pour ce compte."""
    user.token_version = int(user.token_version or 0) + 1

def require_roles(request: Request, *roles):
    user = current_user(request)
    if user["role"] not in roles: raise HTTPException(status_code=403, detail="Permission insuffisante")
    return user


def ensure_event_organization(db, event_id: int, user: dict):
    """Prevent any non-superadmin account from crossing organization boundaries."""
    from app.models import Event
    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    if user.get("role") != "superadmin" and event.organization_id != user.get("organization_id"):
        # Use 404 to avoid disclosing the existence of another organization's event.
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    return event
