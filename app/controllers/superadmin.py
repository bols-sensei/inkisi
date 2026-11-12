import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Organization, Plan, Subscription, User, Event, AuditLog
from app.schemas import OrganizationCreate, OrganizationStatusUpdate, SubscriptionUpdate, PlanCreate, PlanUpdate
from app.security import require_roles, hash_password, revoke_sessions
from app.services.organizations import create_organization_with_admin

router = APIRouter(prefix="/superadmin")


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:190] or "organisation"


@router.get("/api/organizations")
def organizations(request: Request, db: Session = Depends(get_db)):
    require_roles(request, "superadmin")
    now = datetime.now(timezone.utc)
    rows = db.query(Organization).order_by(Organization.created_at.desc()).all()
    result = []
    for org in rows:
        sub = (db.query(Subscription).options(joinedload(Subscription.plan))
               .filter(Subscription.organization_id == org.id, Subscription.starts_at <= now)
               .order_by(Subscription.starts_at.desc(), Subscription.id.desc()).first())
        upcoming = (db.query(Subscription).options(joinedload(Subscription.plan))
                    .filter(Subscription.organization_id == org.id, Subscription.starts_at > now)
                    .order_by(Subscription.starts_at.asc(), Subscription.id.asc()).first())
        primary_admin = (db.query(User).filter_by(organization_id=org.id, role="admin")
                         .order_by(User.id.asc()).first())
        plan_data = lambda row: None if not row else {
            "id": row.id, "status": row.status, "plan": row.plan.name,
            "plan_code": row.plan.code, "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat(), "event_limit": row.plan.event_limit,
            "advanced_features": row.plan.advanced_features,
        }
        result.append({
            "id": org.id, "name": org.name, "slug": org.slug, "status": org.status,
            "created_at": org.created_at.isoformat(),
            "admin": None if not primary_admin else {"id": primary_admin.id, "name": primary_admin.full_name,
                                                       "username": primary_admin.username, "active": primary_admin.active},
            "users": db.query(User).filter_by(organization_id=org.id).count(),
            "events": db.query(Event).filter_by(organization_id=org.id).count(),
            "subscription": plan_data(sub), "upcoming_subscription": plan_data(upcoming),
        })
    return result


@router.post("/api/organizations", status_code=201)
def create_organization(request: Request, payload: OrganizationCreate, db: Session = Depends(get_db)):
    me = require_roles(request, "superadmin")
    # L'e-mail est facultatif ici : le superadmin se porte garant du compte (adresse considérée comme vérifiée).
    org, admin, sub = create_organization_with_admin(
        db, name=payload.name, username=payload.admin_username, full_name=payload.admin_full_name,
        password=payload.admin_password, email=payload.admin_email, email_verified=True, require_email=False)
    db.add(AuditLog(user_id=me["id"], organization_id=org.id, event_id=None, action="platform.organization.created", details=f"{org.name} (admin {admin.username})"))
    db.commit()
    return {"id": org.id, "name": org.name, "slug": org.slug,
            "admin": {"id": admin.id, "username": admin.username},
            "subscription": {"status": "trial", "starts_at": sub.starts_at.isoformat(),
                             "ends_at": sub.ends_at.isoformat(), "plan": "trial"}}


@router.patch("/api/organizations/{organization_id}/status")
def set_organization_status(organization_id: int, payload: OrganizationStatusUpdate, request: Request, db: Session = Depends(get_db)):
    """Suspension totale : plus aucune connexion pour les comptes de l'organisation, effet immédiat."""
    me = require_roles(request, "superadmin")
    org = db.query(Organization).filter_by(id=organization_id).first()
    if not org: raise HTTPException(404, "Organisation introuvable.")
    if me.get("organization_id") == org.id: raise HTTPException(409, "Action refusée sur votre propre organisation.")
    org.status = payload.status
    db.add(AuditLog(user_id=me["id"], organization_id=org.id, event_id=None, action=f"platform.organization.{payload.status}", details=f"{org.name}: {payload.reason}".strip(": ")))
    db.commit()
    return {"id": org.id, "status": org.status}


@router.get("/api/plans")
def plans(request: Request, db: Session = Depends(get_db)):
    require_roles(request, "superadmin")
    return [{"id": p.id, "code": p.code, "name": p.name, "event_limit": p.event_limit,
             "advanced_features": p.advanced_features, "active": p.active}
            for p in db.query(Plan).order_by(Plan.id).all()]


@router.put("/api/plans/{plan_id}")
def update_plan(plan_id: int, payload: PlanUpdate, request: Request, db: Session = Depends(get_db)):
    me = require_roles(request, "superadmin")
    plan = db.query(Plan).filter_by(id=plan_id).first()
    if not plan:
        raise HTTPException(404, "Formule introuvable.")
    if plan.code == "internal":
        raise HTTPException(409, "La formule interne de la plateforme est protégée.")
    if plan.code == "trial" and not payload.active:
        raise HTTPException(409, "La formule d’essai doit rester active pour les nouvelles organisations.")
    plan.name = payload.name.strip()
    plan.event_limit = payload.event_limit
    plan.advanced_features = payload.advanced_features
    plan.active = payload.active
    db.add(AuditLog(user_id=me["id"], organization_id=None, event_id=None, action="platform.plan.updated",
                    details=f"{plan.code}: {plan.name}; quota={plan.event_limit}; avancé={plan.advanced_features}; active={plan.active}"))
    db.commit()
    return {"id": plan.id, "code": plan.code, "name": plan.name, "event_limit": plan.event_limit,
            "advanced_features": plan.advanced_features, "active": plan.active}


@router.get("/api/subscriptions")
def subscriptions(request: Request, db: Session = Depends(get_db)):
    require_roles(request, "superadmin")
    rows = (db.query(Subscription).options(joinedload(Subscription.plan), joinedload(Subscription.organization))
            .order_by(Subscription.starts_at.desc(), Subscription.id.desc()).all())
    now = datetime.now(timezone.utc)
    # Les lignes sont déjà triées par début décroissant : la première période démarrée par organisation est effective.
    seen_orgs = set()
    current_ids = set()
    for row in rows:
        starts = row.starts_at if row.starts_at.tzinfo else row.starts_at.replace(tzinfo=timezone.utc)
        if starts <= now and row.organization_id not in seen_orgs:
            current_ids.add(row.id)
            seen_orgs.add(row.organization_id)
    return [{"id": s.id, "organization_id": s.organization_id, "organization": s.organization.name,
             "organization_status": s.organization.status, "plan_code": s.plan.code, "plan": s.plan.name,
             "event_limit": s.plan.event_limit, "advanced_features": s.plan.advanced_features,
             "status": s.status, "current": s.id in current_ids,
             "starts_at": s.starts_at.isoformat(), "ends_at": s.ends_at.isoformat()}
            for s in rows]


@router.post("/api/plans", status_code=201)
def create_plan(request: Request, payload: PlanCreate, db: Session = Depends(get_db)):
    require_roles(request, "superadmin")
    code = payload.code.strip().lower()
    name = payload.name.strip()
    limit = payload.event_limit
    advanced = payload.advanced_features
    if not re.fullmatch(r"[a-z0-9_-]{2,40}", code) or not name:
        raise HTTPException(422, "Code et nom de formule invalides.")
    if db.query(Plan).filter_by(code=code).first():
        raise HTTPException(409, "Ce code de formule existe déjà.")
    plan = Plan(code=code, name=name, event_limit=limit, advanced_features=advanced, active=True)
    db.add(plan); db.commit()
    return {"id": plan.id, "code": plan.code, "name": plan.name,
            "event_limit": plan.event_limit, "advanced_features": plan.advanced_features}


@router.put("/api/organizations/{organization_id}/subscription")
def update_subscription(organization_id: int, request: Request, payload: SubscriptionUpdate,
                       db: Session = Depends(get_db)):
    me = require_roles(request, "superadmin")
    org = db.query(Organization).filter_by(id=organization_id).first()
    plan = db.query(Plan).filter_by(code=payload.plan_code, active=True).first()
    if not org or not plan:
        raise HTTPException(404, "Organisation ou formule active introuvable.")
    try:
        starts = datetime.fromisoformat(payload.starts_at) if payload.starts_at else datetime.now(timezone.utc)
        ends = datetime.fromisoformat(payload.ends_at)
    except ValueError:
        raise HTTPException(422, "Dates invalides : utilisez un format ISO 8601.")
    if starts.tzinfo is None: starts = starts.replace(tzinfo=timezone.utc)
    if ends.tzinfo is None: ends = ends.replace(tzinfo=timezone.utc)
    if ends <= starts:
        raise HTTPException(422, "La date de fin doit être postérieure à la date de début.")
    sub = Subscription(organization_id=org.id, plan_id=plan.id, status=payload.status,
                       starts_at=starts, ends_at=ends)
    db.add(sub)
    db.add(AuditLog(user_id=me["id"], organization_id=org.id, event_id=None, action="platform.subscription.set", details=f"{org.name}: {plan.code} {payload.status} jusqu'au {ends.date()}"))
    db.commit()
    return {"message": "Abonnement mis à jour manuellement.", "organization_id": org.id,
            "plan": plan.code, "status": sub.status,
            "starts_at": starts.isoformat(), "ends_at": ends.isoformat()}


# ----------------------- Console plateforme -----------------------
from pydantic import BaseModel, Field
from sqlalchemy import func
from app.models import Invitation, EntryRecord, ConferenceRegistration


@router.get("/api/stats")
def platform_stats(request: Request, db: Session = Depends(get_db)):
    require_roles(request, "superadmin")
    now = datetime.now(timezone.utc)
    months = []
    year, month = now.year, now.month
    for _ in range(6):
        months.append((year, month))
        month -= 1
        if month == 0:
            year -= 1; month = 12
    signups = {f"{y:04d}-{m:02d}": 0 for y, m in months}
    for created in db.query(Organization.created_at).all():
        value = created[0]
        if value:
            key = value.strftime("%Y-%m")
            if key in signups: signups[key] += 1
    names = {o.id: o.name for o in db.query(Organization).all()}
    recent = db.query(Event).order_by(Event.id.desc()).limit(6).all()
    return {"organizations": len(names), "users": db.query(User).count(), "events": db.query(Event).count(),
            "invitations": db.query(Invitation).count(), "registrations": db.query(ConferenceRegistration).count(),
            "entries": int(db.query(func.coalesce(func.sum(EntryRecord.quantity), 0)).scalar() or 0),
            "recent_events": [{"id": e.id, "name": e.name, "event_date": e.event_date, "event_type": e.event_type, "organization": names.get(e.organization_id, "—")} for e in recent],
            "organization_signups": [{"period": f"{y:04d}-{m:02d}", "label": f"{['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'][m - 1]} {y}", "count": signups[f"{y:04d}-{m:02d}"]} for y, m in reversed(months)]}


@router.get("/api/organizations/{organization_id}/detail")
def organization_detail(organization_id: int, request: Request, db: Session = Depends(get_db)):
    require_roles(request, "superadmin")
    if not db.query(Organization).filter_by(id=organization_id).first(): raise HTTPException(404, "Organisation introuvable.")
    users = db.query(User).filter_by(organization_id=organization_id).order_by(User.id).all()
    events = db.query(Event).filter_by(organization_id=organization_id).order_by(Event.id.desc()).all()
    return {"users": [{"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role, "active": u.active} for u in users],
            "events": [{"id": e.id, "name": e.name, "event_date": e.event_date, "event_type": e.event_type, "status": e.status} for e in events]}


class UserAdminUpdate(BaseModel):
    active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=200)


@router.patch("/api/users/{user_id}")
def admin_update_user(user_id: int, payload: UserAdminUpdate, request: Request, db: Session = Depends(get_db)):
    me = require_roles(request, "superadmin")
    user = db.query(User).filter_by(id=user_id).first()
    if not user: raise HTTPException(404, "Compte introuvable.")
    if user.id == me["id"] and payload.active is False: raise HTTPException(409, "Vous ne pouvez pas désactiver votre propre compte.")
    if payload.active is not None: user.active = payload.active
    if payload.password: user.password_hash = hash_password(payload.password)
    if payload.active is not None or payload.password: revoke_sessions(user)  # effet immédiat
    db.add(AuditLog(user_id=me["id"], organization_id=user.organization_id, event_id=None, action="platform.user.updated",
                    details=f"{user.username}: active={payload.active} mot_de_passe={'oui' if payload.password else 'non'}"))
    db.commit()
    return {"id": user.id, "active": user.active}
