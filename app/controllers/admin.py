from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from io import BytesIO
import secrets
from app.database import get_db
from app.models import User, Event, EventAssignment, Invitation, EntryRecord, AuditLog, ConferenceRegistration, ConferenceCheckin, Organization
from app.services.messaging import notify_user
from app.security import require_roles, hash_password, revoke_sessions
from app.services.importer import parse_guest_file
from app.services.exports import create_designer_zip, generate_participants_document
from app.schemas import EventCreate, UserCreate, UserUpdate, AssignmentCreate
from app.services.subscriptions import (ensure_event_quota, ensure_can_write, ensure_feature, subscription_state, events_used, GRACE_DAYS)
from app.services.accounts import normalize_email, valid_email
from app.services.organizations import username_taken
router=APIRouter(prefix='/admin')

def _admin(request):
    return require_roles(request, 'admin', 'superadmin')

def _scoped(query, model, user):
    if user.get('role') != 'superadmin':
        org_id = user.get('organization_id')
        if not org_id:
            raise HTTPException(403, 'Aucune organisation n’est associée à ce compte.')
        query = query.filter(model.organization_id == org_id)
    return query

def _event_or_404(db, event_id, user):
    event = _scoped(db.query(Event), Event, user).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, 'Événement introuvable.')
    return event

def audit(db,user,event_id,action,details=''):
    db.add(AuditLog(user_id=user['id'],event_id=event_id,action=action,details=details))

@router.get('/api/overview')
def overview(request: Request, db: Session=Depends(get_db)):
    u=_admin(request); events=_scoped(db.query(Event),Event,u).order_by(Event.id.desc()).all()
    return {'events':[{'id':e.id,'name':e.name,'event_date':e.event_date,'venue':e.venue,'status':e.status,'event_type':e.event_type,'invitations':len(e.invitations),'registrations':db.query(ConferenceRegistration).filter_by(event_id=e.id).count()} for e in events], 'users':_scoped(db.query(User),User,u).count()}

@router.post('/api/events')
def create_event(request: Request, payload: EventCreate, db: Session=Depends(get_db)):
    u=_admin(request); name=payload.name.strip()
    if not name: raise HTTPException(422,'Le nom de l’événement est obligatoire.')
    if payload.event_type=='wedding' and payload.capacity is not None: raise HTTPException(422,'La capacité maximale est réservée aux conférences.')
    org_id = payload.organization_id or u.get('organization_id')
    if u.get('role') != 'superadmin' and payload.organization_id not in (None, u.get('organization_id')):
        raise HTTPException(403, 'Vous ne pouvez pas créer un événement dans une autre organisation.')
    if not org_id:
        raise HTTPException(422, 'Sélectionnez une organisation pour cet événement.')
    if payload.event_type == 'conference': ensure_feature(db, u, org_id, 'advanced_features')
    ensure_event_quota(db, org_id)

    # Gestion temporelle simplifiée : date/heure début et fin
    start_date = payload.start_date.strip() if payload.start_date else ""
    start_time = payload.start_time.strip() if payload.start_time else ""
    end_date = payload.end_date.strip() if payload.end_date else ""
    end_time = payload.end_time.strip() if payload.end_time else ""
    event_date = payload.event_date.strip()
    if not event_date and start_date:
        event_date = f"{start_date} {start_time}".strip()

    e = Event(
        name=name,
        event_date=event_date,
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        venue=payload.venue.strip(),
        status='draft',
        organization_id=org_id,
        event_type=payload.event_type,
        capacity=payload.capacity,
        registration_open=False,
        registration_token=secrets.token_urlsafe(32) if payload.event_type == 'conference' else None
    )
    db.add(e); db.flush(); audit(db,u,e.id,'event.created',name); db.commit()
    return {
        'id': e.id,
        'name': e.name,
        'event_date': e.event_date,
        'start_date': e.start_date,
        'start_time': e.start_time,
        'end_date': e.end_date,
        'end_time': e.end_time,
        'event_type': e.event_type,
        'capacity': e.capacity,
        'registration_token': e.registration_token,
        'registration_url': f'/conference/{e.registration_token}' if e.registration_token else None
    }

from pydantic import BaseModel, Field
class EventUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    event_date: str = Field(default='', max_length=40)
    start_date: str = Field(default='', max_length=20)
    start_time: str = Field(default='', max_length=10)
    end_date: str = Field(default='', max_length=20)
    end_time: str = Field(default='', max_length=10)
    venue: str = Field(default='', max_length=240)
    status: str | None = Field(default=None, pattern='^(draft|active|closed)$')

@router.patch('/api/events/{event_id}')
def update_event(event_id:int,payload:EventUpdate,request:Request,db:Session=Depends(get_db)):
    u=_admin(request); e=_event_or_404(db,event_id,u); ensure_can_write(db,u,e.organization_id)
    e.name=payload.name.strip()
    if payload.start_date:
        e.start_date = payload.start_date.strip()
    if payload.start_time:
        e.start_time = payload.start_time.strip()
    if payload.end_date:
        e.end_date = payload.end_date.strip()
    if payload.end_time:
        e.end_time = payload.end_time.strip()
    e.event_date=payload.event_date.strip() if payload.event_date.strip() else (f"{e.start_date} {e.start_time}".strip() if e.start_date else e.event_date)
    e.venue=payload.venue.strip()
    if payload.status is not None:
        e.status=payload.status
    audit(db,u,event_id,'event.updated',f'{e.name}|{e.event_date}|{e.venue}|{e.status}'); db.commit()
    return {'id':e.id,'status':e.status,'start_date':e.start_date,'start_time':e.start_time,'end_date':e.end_date,'end_time':e.end_time}


class EventStatusUpdate(BaseModel):
    status: str = Field(pattern='^(active|closed)$')


@router.patch('/api/events/{event_id}/status')
def update_event_status(event_id: int, payload: EventStatusUpdate, request: Request, db: Session = Depends(get_db)):
    user = require_roles(request, 'admin', 'superadmin', 'supervisor')
    event = _event_or_404(db, event_id, user)
    if user['role'] == 'supervisor':
        assigned = db.query(EventAssignment.id).filter_by(event_id=event_id, user_id=user['id']).first()
        if not assigned:
            raise HTTPException(403, 'Cet événement ne vous est pas attribué.')
        if payload.status != 'active' or event.status == 'closed':
            raise HTTPException(403, 'Un superviseur peut lancer un événement, mais pas le clôturer ni le rouvrir.')
    else:
        ensure_can_write(db, user, event.organization_id)
    if payload.status == 'closed' and event.status != 'active':
        raise HTTPException(409, 'L’événement doit être lancé avant de pouvoir être clôturé.')
    event.status = payload.status
    audit(db, user, event_id, 'event.status.updated', payload.status)
    db.commit()
    return {'id': event.id, 'status': event.status}

@router.get('/api/events/{event_id}')
def event_detail(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent')  # session et JWT Bearer.
    e=_event_or_404(db,event_id,u)
    e=db.query(Event).options(joinedload(Event.invitations),joinedload(Event.assignments).joinedload(EventAssignment.user)).filter_by(id=e.id).first()
    if u.get('role') not in {'admin','superadmin'} and not any(a.user_id==u.get('id') for a in e.assignments): raise HTTPException(403,'Événement non attribué à ce compte.')
    invs=sorted(e.invitations,key=lambda x:x.sequence_no)
    registration_count=db.query(ConferenceRegistration).filter_by(event_id=e.id).count()
    accepted_count=db.query(ConferenceRegistration).filter_by(event_id=e.id,status='accepted').count()
    checked_in_count=db.query(ConferenceCheckin).filter_by(event_id=e.id).count()
    return {
        'id': e.id,
        'name': e.name,
        'event_date': e.event_date,
        'start_date': e.start_date,
        'start_time': e.start_time,
        'end_date': e.end_date,
        'end_time': e.end_time,
        'venue': e.venue,
        'status': e.status,
        'event_type': e.event_type,
        'capacity': e.capacity,
        'registration_open': e.registration_open,
        'registration_token': e.registration_token,
        'registrations_count': registration_count,
        'accepted_registrations': accepted_count,
        'checked_in_registrations': checked_in_count,
        'invitations': [{
            'id': i.id,
            'sequence_no': i.sequence_no,
            'reference': i.badge_reference,
            'guest_name': i.guest_name,
            'invitation_type': i.invitation_type,
            'quota': i.quota,
            'table_name': i.table_name,
            'status': i.status,
            'entered': sum(r.quantity for r in i.entries),
            'remaining': max(0, i.quota - sum(r.quantity for r in i.entries))
        } for i in invs],
        'assignments': [{
            'id': a.user.id,
            'username': a.user.username,
            'full_name': a.user.full_name,
            'role': a.user.role
        } for a in e.assignments]
    }

@router.post('/api/events/{event_id}/import')
async def import_invitations(event_id:int,request:Request,file:UploadFile=File(...),db:Session=Depends(get_db)):
    u=_admin(request); e=_event_or_404(db,event_id,u); ensure_can_write(db,u,e.organization_id)
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(413,'Fichier trop volumineux (maximum 10 Mo).')
    try: guests,duplicates=parse_guest_file(file.filename or '',content)
    except ValueError as ex: raise HTTPException(422,str(ex))
    if duplicates:
        raise HTTPException(422, 'Doublons de noms détectés dans le fichier : ' + ', '.join(duplicates[:10]) + '. Corrigez ou clarifiez la liste puis réimportez.')
    existing=db.query(Invitation).filter_by(event_id=event_id).count()
    # Import is append-only: existing references are never renumbered.
    created=[]
    for g in guests:
        seq=existing+len(created)+1; ref=f'INV-{seq:04d}'
        inv=Invitation(event_id=event_id,sequence_no=seq,reference=ref,guest_name=g['guest_name'],invitation_type=g['invitation_type'],quota=g['quota'],table_name=g['table_name'],token=secrets.token_urlsafe(32),status='active')
        db.add(inv); created.append(inv)
    # FIX: les doublons bloquent l'import plus haut; ne pas enregistrer un compteur trompeur.
    audit(db,u,event_id,'invitations.imported',f'{len(created)} invitations importées')
    db.commit()
    return {'created':len(created),'duplicates':duplicates,'references':[i.badge_reference for i in created], 'message':f'{len(created)} invitations importées dans l’ordre du fichier.'}

@router.get('/api/events/{event_id}/designer-pack')
def designer_pack(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=_admin(request); e=_event_or_404(db,event_id,u)
    invs=db.query(Invitation).filter_by(event_id=event_id).order_by(Invitation.sequence_no).all()
    if not invs: raise HTTPException(422,'Importez d’abord la liste des invités.')
    data=create_designer_zip(e,invs); audit(db,u,event_id,'designer_pack.generated',f'{len(invs)} invitations'); db.commit()
    return StreamingResponse(BytesIO(data),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="event_{event_id}_designer_pack.zip"'})

@router.get('/api/users')
def list_users(request:Request,db:Session=Depends(get_db)):
    u=_admin(request)
    return [{'id':x.id,'username':x.username,'full_name':x.full_name,'role':x.role,'active':x.active,'email':x.email,'email_verified':x.email_verified}
            for x in _scoped(db.query(User),User,u).order_by(User.id.desc()).all()]

@router.post('/api/users')
def create_user(request:Request,payload:UserCreate,db:Session=Depends(get_db)):
    u=_admin(request); username=payload.username.strip(); full_name=payload.full_name.strip(); password=payload.password; role=payload.role
    if u.get('role')=='superadmin':
        org_id=payload.organization_id
        if not org_id or not db.query(Organization.id).filter_by(id=org_id).first(): raise HTTPException(422,'Indiquez l’organisation du nouveau compte.')
    else: org_id=u.get('organization_id')
    ensure_can_write(db,u,org_id)
    if not username or not full_name or len(password)<10: raise HTTPException(422,'Nom, identifiant et mot de passe de 10 caractères minimum requis.')
    if username_taken(db,username): raise HTTPException(409,'Cet identifiant existe déjà.')
    email=normalize_email(payload.email)
    if email:
        if not valid_email(email): raise HTTPException(422,'Adresse e-mail invalide.')
        if db.query(User.id).filter(User.email==email).first(): raise HTTPException(409,'Cette adresse e-mail est déjà associée à un compte.')
    user=User(username=username,full_name=full_name,password_hash=hash_password(password),role=role,active=True,organization_id=org_id,email=email,email_verified=True)
    db.add(user); db.flush(); audit(db,u,None,'user.created',f'{username} ({role})'); db.commit()
    return {'id':user.id,'username':user.username,'role':user.role}

@router.get('/api/events/{event_id}/participants.pdf')
def export_participants_pdf(event_id: int, request: Request, db: Session = Depends(get_db)):
    """Génération du répertoire officiel des participants inscrits à la conférence (PDF paysage).
    Réservé aux administrateurs autorisés (Invariant 1).
    Ne contient AUCUN programme d'événement : répertoire exclusif de contacts."""
    u = _admin(request)
    e = _event_or_404(db, event_id, u)
    registrations = db.query(ConferenceRegistration).filter_by(event_id=event_id).order_by(ConferenceRegistration.id.asc()).all()
    pdf_bytes = generate_participants_document(e, registrations)
    audit(db, u, event_id, 'participants_document.downloaded', f'{len(registrations)} participants')
    db.commit()
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="participants_evenement_{event_id}.pdf"'}
    )

def _other_active_admins(db,org_id,exclude_id):
    return db.query(User.id).filter(User.organization_id==org_id,User.role=='admin',User.active==True,User.id!=exclude_id).count()

@router.patch('/api/users/{user_id}')
def update_user(user_id:int,payload:UserUpdate,request:Request,db:Session=Depends(get_db)):
    """Gestion d'équipe par l'administrateur de l'organisation (désactivation, rôle, mot de passe, e-mail).
    Volontairement non bloquée par l'abonnement : retirer un accès doit toujours rester possible."""
    u=_admin(request)
    target=_scoped(db.query(User),User,u).filter_by(id=user_id).first()
    if not target: raise HTTPException(404,'Compte introuvable.')
    if target.role=='superadmin': raise HTTPException(403,'Un compte plateforme se gère depuis la console superadministrateur.')
    is_self=target.id==u['id']; revoke=False; changes=[]
    if payload.full_name is not None and payload.full_name.strip()!=target.full_name:
        target.full_name=payload.full_name.strip(); changes.append('nom')
    if payload.role is not None and payload.role!=target.role:
        if is_self: raise HTTPException(409,'Vous ne pouvez pas modifier votre propre rôle.')
        if target.role=='admin' and not _other_active_admins(db,target.organization_id,target.id): raise HTTPException(409,'Au moins un administrateur actif doit rester dans l’organisation.')
        changes.append(f'rôle {target.role}->{payload.role}'); target.role=payload.role; revoke=True
        if payload.role=='admin':  # un admin n'est pas un agent de terrain
            db.query(EventAssignment).filter_by(user_id=target.id).delete()
    if payload.active is not None and payload.active!=target.active:
        if is_self and not payload.active: raise HTTPException(409,'Vous ne pouvez pas désactiver votre propre compte.')
        if not payload.active and target.role=='admin' and not _other_active_admins(db,target.organization_id,target.id): raise HTTPException(409,'Au moins un administrateur actif doit rester dans l’organisation.')
        target.active=payload.active; changes.append('activé' if payload.active else 'désactivé'); revoke=True
    if payload.email is not None:
        email=normalize_email(payload.email)
        if email and not valid_email(email): raise HTTPException(422,'Adresse e-mail invalide.')
        if email and db.query(User.id).filter(User.email==email,User.id!=target.id).first(): raise HTTPException(409,'Cette adresse e-mail est déjà associée à un compte.')
        if email!=target.email: target.email=email; target.email_verified=False; changes.append('e-mail')
    if payload.new_password:
        target.password_hash=hash_password(payload.new_password); changes.append('mot de passe'); revoke=True
    if revoke: revoke_sessions(target)  # effet immédiat sur sessions et JWT déjà émis
    if changes: audit(db,u,None,'user.updated',f'{target.username}: '+', '.join(changes))
    db.commit()
    return {'id':target.id,'username':target.username,'full_name':target.full_name,'role':target.role,'active':target.active,'email':target.email}

@router.get('/api/audit')
def audit_log(request:Request,event_id:int|None=None,action:str|None=Query(default=None,max_length=60),org_id:int|None=None,
              before_id:int|None=Query(default=None,gt=0),limit:int=Query(default=50,ge=1,le=200),db:Session=Depends(get_db)):
    """Journal d'activité de l'organisation (plus récent d'abord, pagination par curseur `before_id`).
    L'administrateur ne voit que sa propre organisation ; le superadmin peut filtrer par `org_id`."""
    u=_admin(request)
    q=db.query(AuditLog,User).join(User,User.id==AuditLog.user_id)
    if u.get('role')=='superadmin':
        if org_id: q=q.filter(AuditLog.organization_id==org_id)
    else: q=q.filter(AuditLog.organization_id==u.get('organization_id'))
    if event_id: q=q.filter(AuditLog.event_id==event_id)
    if action: q=q.filter(AuditLog.action.startswith(action,autoescape=True))
    if before_id: q=q.filter(AuditLog.id<before_id)
    rows=q.order_by(AuditLog.id.desc()).limit(limit+1).all()
    page=rows[:limit]
    org_names = {o.id: o.name for o in db.query(Organization).filter(Organization.id.in_(
        [a.organization_id for a, _ in page if a.organization_id is not None]
    )).all()} if u.get('role') == 'superadmin' and page else {}
    return {'items':[{'id':a.id,'at':a.created_at.isoformat(),'action':a.action,'details':a.details,'event_id':a.event_id,
                      'organization':org_names.get(a.organization_id, 'Plateforme') if u.get('role') == 'superadmin' else None,
                      'user':{'id':usr.id,'username':usr.username,'full_name':usr.full_name}} for a,usr in page],
            'next_before_id':page[-1][0].id if len(rows)>limit and page else None}

@router.get('/api/subscription')
def my_subscription(request:Request,org_id:int|None=None,db:Session=Depends(get_db)):
    u=_admin(request)
    org=org_id if u.get('role')=='superadmin' else u.get('organization_id')
    if not org: raise HTTPException(422,'Indiquez une organisation (org_id).')
    info=subscription_state(db,org); sub=info['subscription']
    if not sub: return {'state':'none'}
    limit=sub.plan.event_limit
    return {'state':info['state'],'status':sub.status,'plan':sub.plan.name,'plan_code':sub.plan.code,'starts_at':sub.starts_at.isoformat() if sub.starts_at else None,'ends_at':info['ends_at'].isoformat() if info['ends_at'] else None,
            'days_left':info['days_left'],'grace_days':GRACE_DAYS,'event_limit':limit,'events_used':events_used(db,org,sub),
            'events_remaining':None if limit<0 else max(0,limit-events_used(db,org,sub)),'advanced_features':sub.plan.advanced_features}

@router.post('/api/events/{event_id}/assignments')
def assign_user(event_id:int,request:Request,payload:AssignmentCreate,db:Session=Depends(get_db)):
    u=_admin(request); e=_event_or_404(db,event_id,u); ensure_can_write(db,u,e.organization_id); user=_scoped(db.query(User),User,u).filter_by(id=payload.user_id,active=True).first()
    if not e or not user: raise HTTPException(404,'Événement ou utilisateur introuvable/inactif.')
    if user.organization_id != e.organization_id: raise HTTPException(403,'Cet utilisateur appartient à une autre organisation.')
    if user.role in {'admin','superadmin'}: raise HTTPException(422,'Un compte administrateur n’est pas affecté comme agent.')
    if db.query(EventAssignment).filter_by(event_id=event_id,user_id=user.id).first(): return {'message':'Cet utilisateur est déjà affecté.'}
    db.add(EventAssignment(event_id=event_id,user_id=user.id)); audit(db,u,event_id,'user.assigned',user.username); db.commit(); notify_user(user.id,e.organization_id,'Affectation à un événement',e.name,event_id,'assignment'); return {'message':'Agent affecté à l’événement.'}


@router.delete('/api/events/{event_id}/assignments/{user_id}')
def unassign_user(event_id:int,user_id:int,request:Request,db:Session=Depends(get_db)):
    u=_admin(request); event=_event_or_404(db,event_id,u)
    assignment=db.query(EventAssignment).filter_by(event_id=event_id,user_id=user_id).first()
    if not assignment: raise HTTPException(404,'Affectation introuvable.')
    target=assignment.user
    db.delete(assignment)
    from app.models import TeamTask, TaskHistory
    tasks=db.query(TeamTask).filter_by(event_id=event_id,assigned_to=user_id).all()
    for task in tasks:
        old=task.assigned_to; task.assigned_to=None
        db.add(TaskHistory(task_id=task.id,user_id=u['id'],action='unassigned',old_value=str(old),new_value='None'))
    audit(db,u,event_id,'user.unassigned',target.username if target else str(user_id)); db.commit()
    return {'message':'Affectation retirée. Les tâches correspondantes sont désormais non affectées.'}
