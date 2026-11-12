import os
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Event, Subscription

GRACE_DAYS = max(0, int(os.getenv("SUBSCRIPTION_GRACE_DAYS", "7")))


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def latest_subscription(db: Session, organization_id: int):
    now = datetime.now(timezone.utc)
    return (db.query(Subscription)
            .filter(Subscription.organization_id == organization_id, Subscription.starts_at <= now)
            .order_by(Subscription.starts_at.desc(), Subscription.id.desc()).first())


def subscription_state(db: Session, organization_id: int) -> dict:
    """État effectif : active | grace | readonly | none.

    - active   : abonnement actif/essai non échu (tout est autorisé).
    - grace    : échu depuis moins de GRACE_DAYS jours (écritures encore autorisées, sauf nouvel événement).
    - readonly : échu au-delà, suspendu ou clos (consultation et exports seulement ; les événements
                 « en cours » restent exploitables au contrôle d'accès).
    """
    now = datetime.now(timezone.utc)
    sub = latest_subscription(db, organization_id)
    if not sub:
        return {"state": "none", "subscription": None, "days_left": None, "ends_at": None}
    ends = _aware(sub.ends_at)
    days_left = None if ends is None else (ends - now).days
    if sub.status in {"trial", "active"}:
        if ends is None or ends > now:
            state = "active"
        elif ends + timedelta(days=GRACE_DAYS) > now:
            state = "grace"
        else:
            state = "readonly"
    else:
        state = "readonly"
    return {"state": state, "subscription": sub, "days_left": days_left, "ends_at": ends}


def active_subscription(db: Session, organization_id: int):
    info = subscription_state(db, organization_id)
    return info["subscription"] if info["state"] == "active" else None


def ensure_can_write(db: Session, user: dict, organization_id: int | None) -> None:
    """Refuse les écritures d'une organisation en lecture seule. Le superadmin n'est jamais bloqué."""
    if user.get("role") == "superadmin" or organization_id is None:
        return
    state = subscription_state(db, organization_id)["state"]
    if state in {"active", "grace"}:
        return
    raise HTTPException(403, "Abonnement expiré ou suspendu : l’organisation est en lecture seule. "
                             "Consultation et exports restent possibles ; le contrôle d’accès des événements en cours n’est pas interrompu.")


def organization_accepts_public_activity(db: Session, organization_id: int | None) -> bool:
    """Formulaires publics (inscriptions conférence) : actifs seulement si l'organisation est exploitable."""
    from app.models import Organization
    if organization_id is None:
        return False
    org = db.query(Organization).filter_by(id=organization_id).first()
    if not org or org.status != "active":
        return False
    return subscription_state(db, organization_id)["state"] in {"active", "grace"}


def ensure_feature(db: Session, user: dict, organization_id: int | None, feature: str = "advanced_features") -> None:
    """Les fonctionnalités de formule sont appliquées côté serveur (le superadmin n'est pas limité)."""
    if user.get("role") == "superadmin" or organization_id is None:
        return
    sub = latest_subscription(db, organization_id)
    if not sub or not getattr(sub.plan, feature, False):
        raise HTTPException(403, "Cette fonctionnalité n’est pas incluse dans la formule de votre organisation.")


def events_used(db: Session, organization_id: int, sub) -> int:
    query = db.query(func.count(Event.id)).filter(Event.organization_id == organization_id)
    if sub is not None:
        if sub.starts_at: query = query.filter(Event.created_at >= sub.starts_at)
        if sub.ends_at: query = query.filter(Event.created_at <= sub.ends_at)
    return int(query.scalar() or 0)


def ensure_event_quota(db: Session, organization_id: int) -> dict:
    info = subscription_state(db, organization_id)
    if info["state"] != "active":
        raise HTTPException(403, "Abonnement inactif ou expiré : la création de nouveaux événements est bloquée. Contactez le superadministrateur.")
    sub = info["subscription"]
    created_count = events_used(db, organization_id, sub)
    limit = sub.plan.event_limit
    if limit >= 0 and created_count >= limit:
        raise HTTPException(403, f"Quota d’événements atteint ({created_count}/{limit}) pour la période d’abonnement.")
    return {"subscription": sub, "created_events": created_count, "event_limit": limit}
