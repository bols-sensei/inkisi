from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Event,
    EventAssignment,
    Invitation,
    EntryRecord,
    AuditLog,
    User,
    ExceptionReview,
    ConferenceRegistration,
    ConferenceCheckin,
)
from app.security import require_roles, ensure_event_organization

router = APIRouter(prefix='/supervisor')


def _ensure_event_access(db: Session, event_id: int, user: dict) -> None:
    """FIX: les superviseurs doivent être affectés; les administrateurs ont accès global."""
    event = ensure_event_organization(db, event_id, user)
    if user['role'] not in {'admin', 'superadmin'}:
        assigned = db.query(EventAssignment.id).filter_by(
            event_id=event_id, user_id=user['id']
        ).first()
        if not assigned:
            raise HTTPException(403, 'Vous n’êtes pas affecté à cet événement.')


@router.get('/api/events')
def my_events(request: Request, db: Session = Depends(get_db)):
    u = require_roles(request, 'supervisor', 'agent')
    ids = [a.event_id for a in db.query(EventAssignment).filter_by(user_id=u['id']).all()]
    events = db.query(Event).filter(Event.id.in_(ids), Event.organization_id == u.get('organization_id')).all() if ids else []
    event_ids = [e.id for e in events]
    invitation_counts = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in db.query(
        Invitation.event_id, func.count(Invitation.id), func.coalesce(func.sum(Invitation.quota), 0)
    ).filter(Invitation.event_id.in_(event_ids)).group_by(Invitation.event_id).all()} if event_ids else {}
    entry_totals = {r[0]: int(r[1] or 0) for r in db.query(
        EntryRecord.event_id, func.coalesce(func.sum(EntryRecord.quantity), 0)
    ).filter(EntryRecord.event_id.in_(event_ids)).group_by(EntryRecord.event_id).all()} if event_ids else {}
    accepted_conf = {r[0]: int(r[1] or 0) for r in db.query(
        ConferenceRegistration.event_id, func.count(ConferenceRegistration.id)
    ).filter(ConferenceRegistration.event_id.in_(event_ids), ConferenceRegistration.status == 'accepted').group_by(ConferenceRegistration.event_id).all()} if event_ids else {}
    total_conf = {r[0]: int(r[1] or 0) for r in db.query(
        ConferenceRegistration.event_id, func.count(ConferenceRegistration.id)
    ).filter(ConferenceRegistration.event_id.in_(event_ids)).group_by(ConferenceRegistration.event_id).all()} if event_ids else {}
    checked_conf = {r[0]: int(r[1] or 0) for r in db.query(
        ConferenceCheckin.event_id, func.count(ConferenceCheckin.id)
    ).filter(ConferenceCheckin.event_id.in_(event_ids)).group_by(ConferenceCheckin.event_id).all()} if event_ids else {}
    pending_reviews = {r[0]: int(r[1] or 0) for r in db.query(
        ExceptionReview.event_id, func.count(ExceptionReview.id)
    ).filter(ExceptionReview.event_id.in_(event_ids), ExceptionReview.status == 'pending').group_by(ExceptionReview.event_id).all()} if event_ids else {}
    assigned_agents = {r[0]: int(r[1] or 0) for r in db.query(
        EventAssignment.event_id, func.count(func.distinct(EventAssignment.user_id))
    ).join(User, User.id == EventAssignment.user_id).filter(
        EventAssignment.event_id.in_(event_ids), User.role == 'agent', User.active.is_(True)
    ).group_by(EventAssignment.event_id).all()} if event_ids else {}
    result = []
    for e in events:
        if e.event_type == 'conference':
            expected = accepted_conf.get(e.id, 0)
            entered = checked_conf.get(e.id, 0)
            invitations = total_conf.get(e.id, 0)
        else:
            invitations, expected = invitation_counts.get(e.id, (0, 0))
            entered = entry_totals.get(e.id, 0)
        result.append({
            'id': e.id,
            'name': e.name,
            'event_date': e.event_date,
            'venue': e.venue,
            'status': e.status,
            'event_type': e.event_type,
            'invitations': invitations,
            'expected': expected,
            'entered': entered,
            'remaining': max(0, expected - entered),
            'pending_exceptions': pending_reviews.get(e.id, 0),
            'agent_count': assigned_agents.get(e.id, 0),
        })
    return result


@router.get('/api/events/{event_id}/dashboard')
def dashboard(event_id: int, request: Request, db: Session = Depends(get_db)):
    u = require_roles(request, 'supervisor', 'agent')
    ensure_event_organization(db, event_id, u)
    a = db.query(EventAssignment).filter_by(event_id=event_id, user_id=u['id']).first()
    if not a:
        raise HTTPException(403, 'Événement non attribué.')
    e = db.query(Event).filter_by(id=event_id).first()
    if not e:
        raise HTTPException(404, 'Événement introuvable.')
    invs = db.query(Invitation).options(joinedload(Invitation.entries)).filter_by(event_id=event_id).all()
    records = (
        db.query(EntryRecord)
        .options(joinedload(EntryRecord.invitation))
        .filter_by(event_id=event_id)
        .order_by(EntryRecord.created_at.desc())
        .limit(30)
        .all()
    )
    if e.event_type == 'conference':
        accepted = db.query(ConferenceRegistration).filter_by(event_id=e.id, status='accepted').count()
        entered = db.query(ConferenceCheckin).filter_by(event_id=e.id).count()
        total = accepted
        invitation_count = db.query(ConferenceRegistration).filter_by(event_id=e.id).count()
    else:
        total = sum(i.quota for i in invs)
        entered = sum(r.quantity for i in invs for r in i.entries)
        invitation_count = len(invs)
    users = {x.id: x for x in db.query(User).filter(User.organization_id == u.get('organization_id')).all()}
    return {
        'event': {'id': e.id, 'name': e.name, 'event_date': e.event_date, 'venue': e.venue},
        'expected': total,
        'entered': entered,
        'remaining': max(0, total - entered),
        'invitation_count': invitation_count,
        'recent_entries': [
            {
                'reference': r.invitation.reference,
                'guest_name': r.invitation.guest_name,
                'quantity': r.quantity,
                'method': r.method,
                'note': r.note,
                'agent': users.get(r.created_by).full_name if users.get(r.created_by) else '—',
                'created_at': r.created_at.isoformat(),
            }
            for r in records
        ],
    }


@router.get('/api/events/{event_id}/agents')
def agents(event_id: int, request: Request, db: Session = Depends(get_db)):
    u = require_roles(request, 'supervisor', 'agent')
    ensure_event_organization(db, event_id, u)
    a = db.query(EventAssignment).filter_by(event_id=event_id, user_id=u['id']).first()
    if not a:
        raise HTTPException(403, 'Événement non attribué.')
    assignments = (
        db.query(EventAssignment)
        .options(joinedload(EventAssignment.user))
        .filter_by(event_id=event_id)
        .all()
    )
    return [
        {
            'id': x.user.id,
            'name': x.user.full_name,
            'username': x.user.username,
            'role': x.user.role,
            'active': x.user.active,
        }
        for x in assignments
    ]


@router.get('/api/events/{event_id}/activity')
def event_activity(event_id: int, request: Request, db: Session = Depends(get_db)):
    # FIX: route de supervision manquante; réservée aux superviseurs et administrateurs.
    u = require_roles(request, 'supervisor', 'admin', 'superadmin')
    _ensure_event_access(db, event_id, u)

    aggregates = (
        db.query(
            EntryRecord.created_by.label('user_id'),
            func.count(EntryRecord.id).label('entries'),
            func.coalesce(func.sum(EntryRecord.quantity), 0).label('people'),
            func.max(EntryRecord.created_at).label('last_activity'),
        )
        .filter(EntryRecord.event_id == event_id)
        .group_by(EntryRecord.created_by)
        .all()
    )
    methods_by_user: dict[int, set[str]] = {}
    for user_id, method in (
        db.query(EntryRecord.created_by, EntryRecord.method)
        .filter(EntryRecord.event_id == event_id)
        .distinct()
        .all()
    ):
        methods_by_user.setdefault(user_id, set()).add(method)

    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([row.user_id for row in aggregates])).all()
    } if aggregates else {}

    return [
        {
            'full_name': users[row.user_id].full_name if row.user_id in users else 'Compte supprimé',
            'entries': int(row.entries or 0),
            'people': int(row.people or 0),
            'last_activity': row.last_activity.isoformat() if row.last_activity else None,
            'methods': sorted(methods_by_user.get(row.user_id, set())),
        }
        for row in aggregates
    ]


@router.get('/api/events/{event_id}/exceptions')
def event_exceptions(event_id: int, request: Request, db: Session = Depends(get_db)):
    # FIX: route de consultation des exceptions, réservée aux superviseurs et administrateurs.
    u = require_roles(request, 'supervisor', 'admin', 'superadmin')
    _ensure_event_access(db, event_id, u)

    reviews = (
        db.query(ExceptionReview)
        .options(joinedload(ExceptionReview.invitation), joinedload(ExceptionReview.user))
        .filter(ExceptionReview.event_id == event_id)
        .order_by(ExceptionReview.created_at.desc())
        .all()
    )
    return [
        {
            'reference': review.invitation.reference,
            'guest_name': review.invitation.guest_name,
            'agent': review.user.full_name,
            'reason': review.reason,
            'decision': review.decision,
            'status': review.status,
            'created_at': review.created_at.isoformat(),
        }
        for review in reviews
    ]
