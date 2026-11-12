"""Configuration d'exécution. Échoue fermé : sans ENVIRONMENT explicite, l'application se comporte comme en production."""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

if not ("PYTEST_CURRENT_TEST" in os.environ and "ENVIRONMENT" not in os.environ):
    load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()
if ENVIRONMENT not in {"development", "production"}:
    raise RuntimeError("ENVIRONMENT doit valoir « development » ou « production » (défaut : production).")


def is_production() -> bool:
    return ENVIRONMENT == "production"


def public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def validate_production_config() -> None:
    """Refuse de démarrer en production avec une configuration incomplète ou incohérente."""
    if not is_production():
        return

    secret = os.getenv("SECRET_KEY", "")
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret) < 32 or len(jwt_secret) < 32:
        raise RuntimeError("SECRET_KEY et JWT_SECRET_KEY doivent contenir au moins 32 caractères aléatoires.")
    if secret == jwt_secret:
        raise RuntimeError("SECRET_KEY et JWT_SECRET_KEY doivent être deux secrets différents.")

    if not os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("PostgreSQL est obligatoire en production.")
    if not os.getenv("RATE_LIMIT_REDIS_URL", "").strip():
        raise RuntimeError("Configurez RATE_LIMIT_REDIS_URL pour le rate limiting partagé.")

    hosts = [host.strip().lower() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]
    if not hosts or "*" in hosts:
        raise RuntimeError("Configurez ALLOWED_HOSTS avec les domaines autorisés, sans joker.")
    public_url = urlparse(public_base_url())
    if public_url.scheme != "https" or not public_url.hostname:
        raise RuntimeError("PUBLIC_BASE_URL doit être une URL HTTPS complète en production.")
    if public_url.hostname.lower() not in {host.split(":", 1)[0].strip("[]") for host in hosts}:
        raise RuntimeError("Le domaine de PUBLIC_BASE_URL doit figurer dans ALLOWED_HOSTS.")

    if not os.getenv("ADMIN_USERNAME", "").strip():
        raise RuntimeError("Définissez explicitement ADMIN_USERNAME pour le compte superadministrateur.")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if len(admin_password) < 16 or admin_password == "ChangeMe-123!":
        raise RuntimeError("ADMIN_PASSWORD doit contenir au moins 16 caractères et ne pas être une valeur par défaut.")
    if os.getenv("ADMIN_SYNC_PASSWORD", "false").lower() == "true":
        raise RuntimeError("ADMIN_SYNC_PASSWORD=true est interdit en production.")

    try:
        if int(os.getenv("SESSION_MAX_AGE_SECONDS", "43200")) < 300:
            raise ValueError
        if int(os.getenv("TRUSTED_PROXY_COUNT", "0")) < 0:
            raise ValueError
    except ValueError as exc:
        raise RuntimeError("SESSION_MAX_AGE_SECONDS et TRUSTED_PROXY_COUNT doivent être des entiers valides.") from exc

    vapid_public = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    vapid_private = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    vapid_subject = os.getenv("VAPID_SUBJECT", "").strip()
    if (vapid_public or vapid_private) and not all((vapid_public, vapid_private, vapid_subject)):
        raise RuntimeError("Configurez ensemble VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY et VAPID_SUBJECT, ou laissez-les tous vides.")
