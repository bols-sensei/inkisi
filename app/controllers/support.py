from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Organization, SupportMessage, SupportTicket, User
from app.security import require_roles

router = APIRouter(prefix='/support')


def _ticket(db, ticket_id, user):
    q = db.query(SupportTicket).filter_by(id=ticket_id)
    if user['role'] != 'superadmin':
        q = q.filter_by(organization_id=user['organization_id'])
    ticket = q.first()
    if not ticket:
        raise HTTPException(404, 'Demande introuvable.')
    return ticket


@router.get('/api/tickets')
def list_tickets(request: Request, db: Session = Depends(get_db)):
    user = require_roles(request, 'admin', 'superadmin')
    q = db.query(SupportTicket)
    if user['role'] != 'superadmin':
        q = q.filter_by(organization_id=user['organization_id'])
    rows = q.order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc()).limit(100).all()
    result = []
    for row in rows:
        org = db.get(Organization, row.organization_id) if user['role'] == 'superadmin' else None
        result.append({'id': row.id, 'subject': row.subject, 'status': row.status,
                       'organization': org.name if org else None,
                       'updated_at': row.updated_at.isoformat()})
    return result


@router.post('/api/tickets', status_code=201)
def create_ticket(payload: dict, request: Request, db: Session = Depends(get_db)):
    user = require_roles(request, 'admin')
    subject = str(payload.get('subject', '')).strip()
    body = str(payload.get('body', '')).strip()
    if not subject or len(subject) > 180 or not body or len(body) > 10000:
        raise HTTPException(422, 'Objet (1 à 180 caractères) et message (1 à 10 000 caractères) requis.')
    now = datetime.now(timezone.utc)
    ticket = SupportTicket(organization_id=user['organization_id'], created_by=user['id'],
                           subject=subject, status='open', created_at=now, updated_at=now)
    db.add(ticket)
    db.flush()
    db.add(SupportMessage(ticket_id=ticket.id, author_id=user['id'], body=body, created_at=now))
    db.commit()
    return {'id': ticket.id, 'subject': ticket.subject, 'status': ticket.status}


@router.get('/api/tickets/{ticket_id}')
def get_ticket(ticket_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_roles(request, 'admin', 'superadmin')
    ticket = _ticket(db, ticket_id, user)
    messages = db.query(SupportMessage, User).join(User, User.id == SupportMessage.author_id).filter(
        SupportMessage.ticket_id == ticket.id).order_by(SupportMessage.id.asc()).all()
    return {'id': ticket.id, 'subject': ticket.subject, 'status': ticket.status,
            'messages': [{'author': row.full_name, 'role': row.role, 'body': msg.body,
                          'created_at': msg.created_at.isoformat()} for msg, row in messages]}


@router.post('/api/tickets/{ticket_id}/messages', status_code=201)
def reply_ticket(ticket_id: int, payload: dict, request: Request, db: Session = Depends(get_db)):
    user = require_roles(request, 'admin', 'superadmin')
    ticket = _ticket(db, ticket_id, user)
    body = str(payload.get('body', '')).strip()
    if not body or len(body) > 10000:
        raise HTTPException(422, 'Le message doit contenir entre 1 et 10 000 caractères.')
    now = datetime.now(timezone.utc)
    db.add(SupportMessage(ticket_id=ticket.id, author_id=user['id'], body=body, created_at=now))
    ticket.updated_at = now
    if ticket.status == 'closed':
        ticket.status = 'open'
    db.commit()
    return {'ok': True}
