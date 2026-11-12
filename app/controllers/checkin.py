from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import EventAssignment, Invitation, EntryRecord, AuditLog, ExceptionReview, Event, ConferenceRegistration, ConferenceCheckin
from app.security import require_roles, ensure_event_organization
from app.schemas import EntryRequest, SyncBatch, ExceptionDecision
from app.services.qr import is_uuid4, looks_like_uuid, parse_payload
router=APIRouter(prefix='/checkin')
def real_scan_time(value):
    """Instant réel du scan hors ligne (ISO 8601). Ignoré s'il est invalide, dans le futur ou vieux de plus de 14 jours."""
    if not value: return None
    try: dt=datetime.fromisoformat(str(value).strip().replace('Z','+00:00'))
    except ValueError: return None
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    now=datetime.now(timezone.utc)
    return dt if now-timedelta(days=14)<=dt<=now+timedelta(minutes=5) else None

def ensure_event_active(event):
    """Le contrôle d'accès n'est possible que pour un événement « en cours » (et jamais interrompu par l'abonnement)."""
    if event.status!='active':
        label={'draft':'en brouillon','closed':'terminé'}.get(event.status,event.status)
        raise HTTPException(409,f'Événement {label} : activez-le (état « En cours ») avant de contrôler les entrées.')

def ensure_assignment(db,event_id,user_id):
    if not db.query(EventAssignment).filter_by(event_id=event_id,user_id=user_id).first(): raise HTTPException(403,'Vous n’êtes pas affecté à cet événement.')
@router.get('/api/events/{event_id}/lookup')
def lookup(event_id:int,request:Request,q:str,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent')
    event=ensure_event_organization(db,event_id,u)
    if u['role'] not in {'admin','superadmin'}: ensure_assignment(db,event_id,u['id'])
    q_str = q.strip()
    if event.event_type == 'conference':
        query = db.query(ConferenceRegistration).filter(ConferenceRegistration.event_id == event_id)
        if q_str.startswith('token:'):
            token_val = q_str[6:].strip()
            if token_val.upper().startswith('BADGE:'):
                _, token_val = parse_payload(token_val)
                if not is_uuid4(token_val):
                    raise HTTPException(422, 'QR invalide : référence UUID v4 attendue.')
            elif token_val.startswith('CONF:'):
                parts = token_val.split(':')
                if len(parts) != 3 or not parts[1].isdigit() or len(parts[2]) < 20 or not all(c.isalnum() or c in '-_' for c in parts[2]):
                    raise HTTPException(422, 'QR de badge invalide.')
                if int(parts[1]) != event_id:
                    return []
                token_val = parts[2]
            if (looks_like_uuid(token_val) and not is_uuid4(token_val)):
                raise HTTPException(422, 'QR invalide : référence UUID v4 attendue.')
            if is_uuid4(token_val):
                query = query.filter(ConferenceRegistration.badge_reference == token_val.lower())
            else:
                query = query.filter(ConferenceRegistration.badge_token == token_val)
        else:
            words = [w for w in q_str.split() if w]
            filters = [
                ConferenceRegistration.badge_reference == q_str,
                ConferenceRegistration.first_name.ilike(f'%{q_str}%'),
                ConferenceRegistration.last_name.ilike(f'%{q_str}%'),
                ConferenceRegistration.full_name.ilike(f'%{q_str}%'),
                ConferenceRegistration.email.ilike(f'%{q_str}%'),
                ConferenceRegistration.phone.ilike(f'%{q_str}%'),
                ConferenceRegistration.profession.ilike(f'%{q_str}%'),
                ConferenceRegistration.organization_name.ilike(f'%{q_str}%')
            ]
            if len(words) >= 2:
                w1, w2 = words[0], words[1]
                filters.append(ConferenceRegistration.first_name.ilike(f'%{w1}%') & ConferenceRegistration.last_name.ilike(f'%{w2}%'))
                filters.append(ConferenceRegistration.first_name.ilike(f'%{w2}%') & ConferenceRegistration.last_name.ilike(f'%{w1}%'))
            query = query.filter(or_(*filters))

        regs = query.order_by(ConferenceRegistration.id.desc()).limit(35).all()
        reg_ids = [r.id for r in regs]
        checkins = {c.registration_id: c for c in db.query(ConferenceCheckin).filter(ConferenceCheckin.registration_id.in_(reg_ids)).all()} if reg_ids else {}

        return [
            {
                'id': r.id,
                'type': 'conference',
                'reference': r.badge_reference,
                'guest_name': r.full_name or f"{r.first_name} {r.last_name}".strip(),
                'first_name': r.first_name,
                'last_name': r.last_name,
                'email': r.email,
                'phone': r.phone,
                'profession': r.profession,
                'organization_name': r.organization_name,
                'category': r.category,
                'photo_data': r.photo_data,
                'has_photo': bool(r.photo_data),
                'badge_token': r.badge_token,
                'status': r.status,
                'is_manual': getattr(r, 'is_manual', False),
                'quota': 1,
                'entered': 1 if r.id in checkins else 0,
                'remaining': 0 if r.id in checkins else 1,
                'checked_in_at': checkins[r.id].checked_in_at.isoformat() if r.id in checkins else None,
                'table_name': '',
                'event_id': event_id,
                'event_name': event.name,
                'badge_url': f"/api/public/conferences/badge/{r.public_token}" if r.status == 'accepted' else None
            }
            for r in regs
        ]
    else:
        query = db.query(Invitation).filter(Invitation.event_id == event_id)
        if q_str.startswith('token:'):
            raw_code = q_str[6:].strip()
            qr_event, token = parse_payload(raw_code)
            if qr_event is not None and qr_event != event_id:
                return []
            if (raw_code.startswith('IA1.') and qr_event is None) or (raw_code.upper().startswith('BADGE:') and not is_uuid4(token)) or (looks_like_uuid(token) and not is_uuid4(token)):
                raise HTTPException(422, 'QR invalide : référence UUID v4 attendue.')
            if is_uuid4(token):
                query = query.filter(Invitation.badge_reference == token.lower())
            else:
                query = query.filter(Invitation.token == token)
        else:
            query = query.filter(Invitation.status == 'active').filter(
                (Invitation.badge_reference.ilike(f'%{q_str}%')) |
                (Invitation.reference.ilike(f'%{q_str}%')) |
                (Invitation.guest_name.ilike(f'%{q_str}%')) |
                (Invitation.table_name.ilike(f'%{q_str}%')) |
                (Invitation.invitation_type.ilike(f'%{q_str}%'))
            )
        invs = query.order_by(Invitation.sequence_no).limit(35).all()
        return [
            {
                'id': i.id,
                'type': 'invitation',
                'reference': i.badge_reference,
                'guest_name': i.guest_name,
                'invitation_type': i.invitation_type,
                'quota': i.quota,
                'entered': sum(x.quantity for x in i.entries),
                'remaining': max(0, i.quota - sum(x.quantity for x in i.entries)),
                'table_name': i.table_name,
                'status': i.status,
                'event_id': event_id,
                'event_name': event.name
            }
            for i in invs
        ]
@router.post('/api/events/{event_id}/entry')
def register_entry(event_id:int,request:Request,payload:EntryRequest,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent')
    event=ensure_event_organization(db,event_id,u)
    if u['role'] not in {'admin','superadmin'}: ensure_assignment(db,event_id,u['id'])
    if payload.idempotency_key:
        prior=db.query(EntryRecord).filter_by(event_id=event_id,idempotency_key=payload.idempotency_key).first()
        if prior:
            if prior.event_id!=event_id or prior.invitation_id!=payload.invitation_id: raise HTTPException(409,'Clé idempotente déjà utilisée pour un autre passage.')
            return {'message':'Passage déjà enregistré.','reference':prior.invitation.badge_reference,'already_registered':True}
    inv=db.query(Invitation).filter_by(id=payload.invitation_id,event_id=event_id).with_for_update().first()
    if not inv: raise HTTPException(404,'Invitation introuvable pour cet événement.')
    # Recheck after taking the invitation lock: a concurrent retry may have committed while waiting.
    if payload.idempotency_key:
        prior=db.query(EntryRecord).filter_by(event_id=event_id,idempotency_key=payload.idempotency_key).first()
        if prior:
            if prior.invitation_id!=payload.invitation_id: raise HTTPException(409,'Idempotency key already used for another entry.')
            return {'message':'Passage d\u00e9j\u00e0 enregistr\u00e9.','reference':prior.invitation.badge_reference,'already_registered':True}
    ensure_event_active(event)
    if inv.status!='active': raise HTTPException(409,'Invitation révoquée ou inactive.')
    try: quantity=int(payload.quantity)
    except Exception: raise HTTPException(422,'Quantité invalide.')
    if quantity<1: raise HTTPException(422,'La quantité doit être supérieure à zéro.')
    entered=db.query(func.coalesce(func.sum(EntryRecord.quantity),0)).filter_by(invitation_id=inv.id).scalar() or 0
    if entered+quantity>inv.quota: raise HTTPException(409,f'Quota dépassé : {inv.quota-entered} personne(s) restante(s).')
    note=(payload.note or '').strip(); method=payload.method
    if method not in {'qr','manual','nfc','offline'}: method='manual'
    rec=EntryRecord(event_id=event_id,invitation_id=inv.id,quantity=quantity,method=method,note=note,created_by=u['id'],idempotency_key=payload.idempotency_key); db.add(rec)
    db.add(AuditLog(event_id=event_id,user_id=u['id'],action='entry.registered',details=f'{inv.reference}; quantity={quantity}; method={method}; note={note}'))
    try: db.commit()
    except IntegrityError:
        db.rollback()
        if payload.idempotency_key:
            prior=db.query(EntryRecord).filter_by(event_id=event_id,idempotency_key=payload.idempotency_key).first()
            if prior and prior.event_id==event_id and prior.invitation_id==payload.invitation_id: return {'message':'Passage déjà enregistré.','reference':prior.invitation.badge_reference,'already_registered':True}
        raise HTTPException(409,'Conflit de synchronisation : passage déjà enregistré.')
    return {'message':'Entrée enregistrée.','reference':inv.badge_reference,'entered':entered+quantity,'remaining':inv.quota-entered-quantity}
@router.post('/api/events/{event_id}/exceptions')
def exception(event_id:int,request:Request,payload:ExceptionDecision,db:Session=Depends(get_db)):
    u=require_roles(request,'supervisor')
    event=ensure_event_organization(db,event_id,u)
    ensure_assignment(db,event_id,u['id'])
    ensure_event_active(event)
    inv=db.query(Invitation).filter_by(id=payload.invitation_id,event_id=event_id).first()
    reason=(payload.reason or '').strip()
    if not inv or len(reason)<8: raise HTTPException(422,'Invitation requise et motif d’au moins 8 caractères.')
    db.add(ExceptionReview(event_id=event_id,invitation_id=inv.id,user_id=u['id'],decision=payload.decision,reason=reason,status='pending' if payload.decision=='review' else payload.decision))
    db.add(AuditLog(event_id=event_id,user_id=u['id'],action='exception.reviewed',details=f'{inv.reference}; decision={payload.decision}; reason={reason}'))
    db.commit(); return {'message':'Décision enregistrée dans l’historique.','reference':inv.badge_reference}


@router.post('/api/sync')
def sync_offline_batch(request: Request, batch: SyncBatch, db: Session=Depends(get_db)):
    """Idempotent synchronization. Conflicts are reported instead of silently overbooking."""
    u=require_roles(request,'admin','superadmin','supervisor','agent')
    results=[]
    for item in batch.entries:
        if item.user_id and item.user_id!=u['id']:
            results.append({'client_id':item.client_id,'status':'deferred','reason':'Passage scanné avec un autre compte : reconnectez-vous avec ce compte pour le synchroniser.'})
            continue
        try:
            event=ensure_event_organization(db,item.event_id,u)
        except HTTPException as exc:
            results.append({'client_id':item.client_id,'status':'rejected','reason':exc.detail})
            continue
        existing=db.query(EntryRecord).filter_by(event_id=item.event_id,idempotency_key=item.client_id).first()
        if existing:
            qr_event,token=parse_payload(item.token)
            if token not in {existing.invitation.token, existing.invitation.badge_reference}:
                results.append({'client_id':item.client_id,'status':'conflict','reason':'Identifiant de synchronisation déjà utilisé pour une autre invitation.'})
            else:
                results.append({'client_id':item.client_id,'status':'already_synced','reference':existing.invitation.badge_reference})
            continue
        if event.status!='active':
            results.append({'client_id':item.client_id,'status':'rejected','reason':'Événement non actif : passage hors ligne refusé.'})
            continue
        if u['role'] not in {'admin','superadmin'}: ensure_assignment(db,item.event_id,u['id'])
        qr_event,token=parse_payload(item.token)
        if qr_event is not None and qr_event!=item.event_id:
            results.append({'client_id':item.client_id,'status':'rejected','reason':'QR non reconnu pour cet événement.'})
            continue
        inv_query=db.query(Invitation).filter(Invitation.event_id == item.event_id)
        if looks_like_uuid(token):
            if not is_uuid4(token):
                results.append({'client_id':item.client_id,'status':'rejected','reason':'Référence UUID de badge invalide.'})
                continue
            inv_query=inv_query.filter(Invitation.badge_reference == token.lower())
        else:
            inv_query=inv_query.filter(Invitation.token == token)
        inv=inv_query.with_for_update().first()
        if not inv or inv.status!='active':
            results.append({'client_id':item.client_id,'status':'rejected','reason':'Invitation introuvable, inactive ou révoquée'})
            continue
        entered=db.query(func.coalesce(func.sum(EntryRecord.quantity),0)).filter_by(invitation_id=inv.id).scalar() or 0
        if entered + item.quantity > inv.quota:
            results.append({'client_id':item.client_id,'status':'conflict','reference':inv.badge_reference,'reason':f'Quota dépassé; {max(0,inv.quota-entered)} place(s) restante(s)'})
            continue
        now=datetime.now(timezone.utc); scanned_at=real_scan_time(item.occurred_at)
        note='Synchronisé depuis un appareil hors ligne'+('' if scanned_at or not item.occurred_at else ' (date de scan invalide : heure de réception utilisée)')
        rec=EntryRecord(event_id=item.event_id,invitation_id=inv.id,quantity=item.quantity,method=item.method,note=note,created_by=u['id'],idempotency_key=item.client_id,
                        created_at=scanned_at or now,synced_at=now)
        db.add(rec)
        # FIX: commit par item pour que chaque passage soit idempotent dès sa synchronisation.
        # En cas de synchronisations concurrentes avec le même client_id, la contrainte UNIQUE peut
        # déclencher IntegrityError; une stratégie de retry/rollback est nécessaire pour ce cas.
        db.flush()
        db.add(AuditLog(event_id=item.event_id,user_id=u['id'],action='entry.synced',details=f'{inv.reference}; client_id={item.client_id}; quantity={item.quantity}; method={item.method}; scanné={(scanned_at or now).isoformat()}'))
        try:
            db.commit()
            results.append({'client_id':item.client_id,'status':'synced','reference':inv.badge_reference,'remaining':max(0,inv.quota-entered-item.quantity)})
        except IntegrityError:
            db.rollback()
            prior=db.query(EntryRecord).filter_by(event_id=item.event_id,idempotency_key=item.client_id).first()
            if prior and prior.event_id==item.event_id:
                results.append({'client_id':item.client_id,'status':'already_synced','reference':prior.invitation.badge_reference})
            else:
                results.append({'client_id':item.client_id,'status':'conflict','reason':'Conflit concurrent : réessayez après synchronisation.'})
    return {'results':results,'synced':sum(x['status'] in {'synced','already_synced'} for x in results),'conflicts':sum(x['status']=='conflict' for x in results)}
