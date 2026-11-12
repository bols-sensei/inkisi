from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import secrets, os, re
from fastapi import APIRouter, Request, Depends, HTTPException, Body, UploadFile, File, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from reportlab.lib.pagesizes import A4
import base64
import json
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from app.database import get_db
from app.models import (Event, Invitation, EntryRecord, User, AuditLog, EventAssignment, ConferenceRegistration, ConferenceCheckin, MemberBadge,
                        EventProgramItem, TeamTask, TaskHistory, Notification, PushSubscription, PushOutbox, EmailVerification)
from app.security import require_roles, ensure_event_organization
from app.services.exports import qr_png
from app.services.qr import build_payload, is_uuid4, looks_like_uuid, new_badge_reference
from app.services.messaging import notify_user, get_vapid_public_key
from app.services.conference import decide_registration_status, process_photo
from app.services.badge import generate_participant_badge_png
from app.services.subscriptions import ensure_event_quota, ensure_can_write, ensure_feature, organization_accepts_public_activity
from app.services.importer import parse_participant_file
from app.config import is_production, public_base_url
from app.services.safe import pdf_text
from app.schemas import InvitationAction
from pydantic import BaseModel, Field

router = APIRouter()

class InvitationIn(BaseModel):
    guest_name: str = Field(min_length=1, max_length=200)
    invitation_type: str = Field(default='individuelle', max_length=30)
    quota: int = Field(default=1, ge=1, le=10000)
    table_name: str = Field(default='', max_length=80)

class RegistrationIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=180)
    last_name: str | None = Field(default=None, max_length=100)
    first_name: str | None = Field(default=None, max_length=100)
    email: str = Field(default='', max_length=254)
    phone: str = Field(default='', max_length=40)
    profession: str | None = Field(default='', max_length=180)
    organization_name: str | None = Field(default='', max_length=180)
    category: str = Field(default='participant', max_length=40)
    photo_data: str | None = Field(default=None)

class ConferenceScanIn(BaseModel):
    badge_reference: str | None = Field(default=None, max_length=128)
    badge_token: str | None = Field(default=None, max_length=128)
    registration_id: int | None = Field(default=None)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=100)
    method: str = Field(default='qr')

class RegistrationStatus(BaseModel):
    status: str = Field(pattern='^(accepted|rejected|cancelled|pending|waitlist)$')

class AdminRegistrationUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    full_name: str | None = Field(default=None, max_length=180)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    profession: str | None = Field(default=None, max_length=180)
    organization_name: str | None = Field(default=None, max_length=180)
    category: str | None = Field(default=None, max_length=40)
    photo_data: str | None = Field(default=None)
    regenerate_qr: bool = False

class ProgramIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default='', max_length=4000)
    starts_at: datetime
    ends_at: datetime
    location: str = Field(default='', max_length=180)
    speaker: str = Field(default='', max_length=180)

class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default='', max_length=4000)
    assigned_to: int | None = None
    status: str = Field(default='todo', pattern='^(todo|in_progress|done|blocked)$')
    priority: str = Field(default='normal', pattern='^(low|normal|high|urgent)$')
    due_at: datetime | None = None


def _ensure_assigned(db,event_id,user):
    if user.get('role') not in ('admin','superadmin') and not db.query(EventAssignment.id).filter_by(event_id=event_id,user_id=user['id']).first():
        raise HTTPException(403,'Vous n’êtes pas affecté à cet événement.')

def _admin_event(db, event_id, user, write=True):
    """Droits admin + événement de l'organisation. `write=True` refuse aussi une organisation en lecture seule (abonnement échu)."""
    if user.get('role') not in ('admin','superadmin'): raise HTTPException(403, 'Droits administrateur requis.')
    event = ensure_event_organization(db, event_id, user)
    if write: ensure_can_write(db, user, event.organization_id)
    return event


def _audit(db, user, event_id, action, details=''):
    db.add(AuditLog(user_id=user['id'], event_id=event_id, action=action, details=details))

def _notify_event_team(db, event, title, body, category='event'):
    for assignment in db.query(EventAssignment).filter_by(event_id=event.id).all():
        notify_user(assignment.user_id,event.organization_id,title,body,event.id,category)


def _capacity_state(db, event):
    accepted = db.query(ConferenceRegistration).filter_by(event_id=event.id, status='accepted').count()
    return accepted, event.capacity if event.capacity is not None else 0


def _promote_waitlist(db, event):
    promoted=[]
    if event.capacity is None: return promoted
    accepted, capacity = _capacity_state(db, event)
    while accepted < capacity:
        candidate = (db.query(ConferenceRegistration).filter_by(event_id=event.id, status='waitlist')
                     .order_by(ConferenceRegistration.created_at.asc(), ConferenceRegistration.id.asc()).first())
        if not candidate: break
        candidate.status = 'accepted'; accepted += 1; promoted.append(candidate)
        for admin in db.query(User).filter(User.organization_id == event.organization_id, User.role.in_(['admin','superadmin'])).all():
            db.add(Notification(user_id=admin.id, organization_id=event.organization_id, event_id=event.id,
                                title='Place libérée : liste d’attente', body=f'{candidate.full_name} a été promu(e) depuis la liste d’attente.', category='conference'))
    return promoted

# ----------------------- Mariage : invitations -----------------------
@router.post('/admin/api/events/{event_id}/invitations', status_code=201)
def create_invitation(event_id: int, payload: InvitationIn, request: Request, db: Session = Depends(get_db)):
    u = require_roles(request, 'admin', 'superadmin'); event = _admin_event(db, event_id, u)
    if not payload.invitation_type.strip(): raise HTTPException(422, 'Le type d’invitation est obligatoire.')
    seq = (db.query(func.max(Invitation.sequence_no)).filter_by(event_id=event_id).scalar() or 0) + 1
    inv = Invitation(event_id=event_id, sequence_no=seq, reference=f'INV-{seq:04d}', badge_reference=new_badge_reference(), guest_name=payload.guest_name.strip(),
                     invitation_type=payload.invitation_type, quota=payload.quota, table_name=payload.table_name.strip(),
                     token=secrets.token_urlsafe(32), status='active')
    db.add(inv); _audit(db,u,event_id,'invitation.created',f'{inv.reference}:{inv.invitation_type}:{inv.quota}'); db.commit()
    return {'id':inv.id,'reference':inv.badge_reference,'token':inv.token,'quota':inv.quota,'type':inv.invitation_type}


@router.patch('/admin/api/events/{event_id}/invitations/{invitation_id}')
def update_invitation(event_id: int, invitation_id: int, payload: InvitationIn, request: Request, db: Session = Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); _admin_event(db,event_id,u)
    inv=db.query(Invitation).filter_by(id=invitation_id,event_id=event_id).first()
    if not inv: raise HTTPException(404,'Invitation introuvable.')
    entered=db.query(func.coalesce(func.sum(EntryRecord.quantity),0)).filter_by(invitation_id=inv.id).scalar() or 0
    if payload.quota < entered: raise HTTPException(409,'Le quota ne peut pas être inférieur au nombre de personnes déjà entrées.')
    old=f'{inv.guest_name}|{inv.invitation_type}|{inv.quota}|{inv.table_name}'
    inv.guest_name=payload.guest_name.strip(); inv.invitation_type=payload.invitation_type; inv.quota=payload.quota; inv.table_name=payload.table_name.strip()
    _audit(db,u,event_id,'invitation.updated',f'{inv.reference}: {old} -> {inv.guest_name}|{inv.invitation_type}|{inv.quota}|{inv.table_name}')
    db.commit(); return {'message':'Invitation mise à jour.'}


def _invitation_or_404(db,event_id,invitation_id):
    inv=db.query(Invitation).filter_by(id=invitation_id,event_id=event_id).first()
    if not inv: raise HTTPException(404,'Invitation introuvable.')
    return inv


@router.post('/admin/api/events/{event_id}/invitations/{invitation_id}/revoke')
def revoke_invitation(event_id:int,invitation_id:int,request:Request,payload:InvitationAction=Body(default=InvitationAction()),db:Session=Depends(get_db)):
    """Invalide immédiatement l'invitation : tout scan (en ligne ou synchronisé plus tard) est refusé."""
    u=require_roles(request,'admin','superadmin'); _admin_event(db,event_id,u); inv=_invitation_or_404(db,event_id,invitation_id)
    if inv.status=='revoked': return {'message':'Invitation déjà révoquée.','status':inv.status}
    inv.status='revoked'; _audit(db,u,event_id,'invitation.revoked',f'{inv.reference}: {payload.reason}'.strip(': ')); db.commit()
    return {'message':'Invitation révoquée.','status':inv.status,'reference':inv.badge_reference}


@router.post('/admin/api/events/{event_id}/invitations/{invitation_id}/restore')
def restore_invitation(event_id:int,invitation_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); _admin_event(db,event_id,u); inv=_invitation_or_404(db,event_id,invitation_id)
    if inv.status=='active': return {'message':'Invitation déjà active.','status':inv.status}
    inv.status='active'; _audit(db,u,event_id,'invitation.restored',inv.reference); db.commit()
    return {'message':'Invitation réactivée.','status':inv.status,'reference':inv.badge_reference}


@router.post('/admin/api/events/{event_id}/invitations/{invitation_id}/regenerate-token')
def regenerate_invitation_token(event_id:int,invitation_id:int,request:Request,payload:InvitationAction=Body(default=InvitationAction()),db:Session=Depends(get_db)):
    """QR compromis ou perdu : l'ancien jeton cesse de fonctionner, un nouveau QR doit être réimprimé."""
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u); inv=_invitation_or_404(db,event_id,invitation_id)
    inv.token=secrets.token_urlsafe(32)
    inv.badge_reference=new_badge_reference()
    _audit(db,u,event_id,'invitation.token_regenerated',f'{inv.reference}: {payload.reason}'.strip(': ')); db.commit()
    return {'message':'Nouveau QR généré. L’ancien QR est désormais refusé.','reference':inv.badge_reference,'qr_payload':build_payload(event.id,inv.badge_reference)}


@router.get('/admin/api/events/{event_id}/invitations.pdf')
def invitations_pdf(event_id: int, request: Request, db: Session = Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False)
    invitations=db.query(Invitation).filter_by(event_id=event_id).order_by(Invitation.sequence_no).all()
    if not invitations: raise HTTPException(404,'Aucune invitation à exporter.')
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=14*mm,leftMargin=14*mm,topMargin=14*mm,bottomMargin=14*mm)
    styles=getSampleStyleSheet(); story=[Paragraph(f'Invitations — {pdf_text(event.name)}',styles['Title']),Spacer(1,5*mm)]
    for inv in invitations:
        story += [Paragraph(f'<b>{pdf_text(inv.guest_name)}</b> — {pdf_text(inv.invitation_type)} — {pdf_text(inv.badge_reference)}',styles['Heading2']),
                  Paragraph(f'Quota autorisé : {inv.quota} personne(s) | Table : {pdf_text(inv.table_name or "Non attribuée")}',styles['BodyText']),
                  Image(BytesIO(qr_png(build_payload(event.id,inv.badge_reference))),width=35*mm,height=35*mm),Spacer(1,5*mm)]
    doc.build(story); _audit(db,u,event_id,'invitations.pdf.generated',str(len(invitations))); db.commit(); buf.seek(0)
    return StreamingResponse(buf,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="invitations_event_{event_id}.pdf"'})

# ----------------------- Conférence : configuration publique -----------------------
@router.get('/admin/api/events/{event_id}/invitations/batch-pdf')
def invitations_batch_pdf(event_id:int,request:Request,db:Session=Depends(get_db)):
    import zipfile
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False); ensure_feature(db,u,event.organization_id,'advanced_features')
    invitations=db.query(Invitation).filter_by(event_id=event_id).order_by(Invitation.sequence_no).all()
    if not invitations: raise HTTPException(404,'Aucune invitation à générer.')
    archive=BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for inv in invitations:
            pdf=BytesIO(); doc=SimpleDocTemplate(pdf,pagesize=(100*mm,150*mm),rightMargin=8*mm,leftMargin=8*mm,topMargin=8*mm,bottomMargin=8*mm)
            styles=getSampleStyleSheet()
            story=[Paragraph(pdf_text(event.name),styles['Title']),Spacer(1,7*mm),Paragraph(pdf_text(inv.guest_name),styles['Heading1']),
                   Paragraph(f'{pdf_text(inv.invitation_type)} · {pdf_text(inv.badge_reference)}',styles['BodyText']),Spacer(1,4*mm),
                   Paragraph(f'Invitation valable pour {inv.quota} personne(s)',styles['BodyText']),Spacer(1,6*mm),
                   Image(BytesIO(qr_png(build_payload(event.id,inv.badge_reference))),width=45*mm,height=45*mm),Spacer(1,5*mm),
                   Paragraph(f'{pdf_text(event.event_date or "")} · {pdf_text(event.venue or "")}',styles['BodyText'])]
            doc.build(story); z.writestr(f'{inv.badge_reference}_{inv.guest_name[:35].replace("/","-")}.pdf',pdf.getvalue())
    _audit(db,u,event_id,'invitations.batch_pdf.generated',str(len(invitations))); db.commit(); archive.seek(0)
    return StreamingResponse(archive,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="invitations_personnalisees_{event_id}.zip"'})


CATEGORIES=[('participant','Participant'),('vip','VIP'),('speaker','Intervenant'),('press','Presse'),('guest','Invité')]
REG_LABELS={'pending':('En attente','warn'),'accepted':('Acceptée','ok'),'waitlist':('Liste d’attente','cobalt'),'rejected':('Refusée','bad'),'cancelled':('Annulée','')}

def _page(request, status_code=200, **ctx):
    return request.app.state.templates.TemplateResponse(request=request, name='conference_public.html', status_code=status_code, context={'user': None, 'program': None, 'places': None, 'subtitle': '', 'categories': CATEGORIES, **ctx})

MEMBER_PALETTES = {
    'royal': ['#1f1a4d', '#cda553', '#f7e6b8'], 'malachite': ['#11463d', '#c97f4b', '#f7d2ae'],
    'graphite': ['#30343b', '#c4c9d1', '#ffffff'], 'burgundy': ['#561225', '#dbb97c', '#fcefd0'],
    'midnight': ['#0e2f52', '#dbb97c', '#fcefd0'], 'noir': ['#17171b', '#cda553', '#f7e6b8'],
}
MEMBER_METALS = [
    ['#f7e6b8','#cda553','#8b6b2b','#ecd48f'], ['#f7d2ae','#c97f4b','#85451f','#f0b98a'],
    ['#ffffff','#c4c9d1','#767d88','#e8ebf0'], ['#fcefd0','#dbb97c','#96703a','#f4deb0'],
]

@router.get('/admin/api/events/{event_id}/member-badges')
def member_badge_settings(event_id: int, request: Request, db: Session = Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False)
    config=json.loads(event.member_badge_config or '{}')
    return {'enabled': bool(event.member_badge_token), 'token': event.member_badge_token,
            'palette': config.get('palette','royal'), 'categories': config.get('categories',['Presse','Protocole','Équipe']),
            'metal': config.get('metal',0), 'shape': config.get('shape','arche'), 'seal': config.get('seal',True),
            'logo_data': config.get('logo_data'),
            'request_count': db.query(MemberBadge.id).filter_by(event_id=event_id).count()}

@router.put('/admin/api/events/{event_id}/member-badges')
def save_member_badge_settings(event_id: int, request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    palette=payload.get('palette'); categories=payload.get('categories'); metal=payload.get('metal',0)
    shape=payload.get('shape','arche'); seal=bool(payload.get('seal',True)); logo_data=payload.get('logo_data')
    if palette not in MEMBER_PALETTES or not isinstance(categories,list): raise HTTPException(422,'Choisissez une palette et des catégories valides.')
    if isinstance(metal,bool) or not isinstance(metal,int) or metal not in range(len(MEMBER_METALS)): raise HTTPException(422,'Choisissez une finition métallique valide.')
    if shape not in {'arche','cercle','carre'}: raise HTTPException(422,'Choisissez une forme de photo valide.')
    if logo_data is not None and (not isinstance(logo_data,str) or len(logo_data)>1_500_000 or not logo_data.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,'))):
        raise HTTPException(422,'Le logo doit être une image PNG, JPEG ou WebP de moins de 1 Mo.')
    if logo_data:
        try:
            from PIL import Image
            raw_logo=base64.b64decode(logo_data.split(',',1)[1],validate=True)
            image=Image.open(BytesIO(raw_logo))
            if image.format not in {'PNG','JPEG','WEBP'} or image.width>3000 or image.height>3000 or image.width*image.height>9_000_000:
                raise ValueError('logo dimensions')
            image.verify()
        except Exception:
            raise HTTPException(422,'Le fichier logo est invalide ou dépasse les dimensions autorisées.')
    categories=[str(x).strip()[:60] for x in categories if str(x).strip()]
    if not categories or len(categories)>8 or len({x.casefold() for x in categories}) != len(categories): raise HTTPException(422,'Ajoutez de 1 à 8 catégories différentes.')
    event.member_badge_config=json.dumps({'palette':palette,'metal':metal,'shape':shape,'seal':seal,'logo_data':logo_data,'categories':categories},ensure_ascii=False)
    if payload.get('enabled') and not event.member_badge_token: event.member_badge_token=secrets.token_urlsafe(24)
    if not payload.get('enabled'): event.member_badge_token=None
    _audit(db,u,event_id,'member_badges.settings.updated',f'palette={palette}; categories={len(categories)}; enabled={bool(event.member_badge_token)}')
    db.commit()
    return {'enabled':bool(event.member_badge_token),'token':event.member_badge_token,'palette':palette,'categories':categories,'metal':metal,'shape':shape,'seal':seal}

@router.get('/member-badge/{token}', response_class=HTMLResponse, include_in_schema=False)
def member_badge_form(token: str, request: Request, db: Session = Depends(get_db)):
    event=db.query(Event).filter_by(member_badge_token=token).first()
    if not event: raise HTTPException(404,'Ce lien de badge membre est introuvable ou désactivé.')
    config=json.loads(event.member_badge_config or '{}')
    return request.app.state.templates.TemplateResponse(request=request,name='member_badge.html',context={'event':event,'categories':config.get('categories',[])})

@router.post('/member-badge/{token}', response_class=HTMLResponse, include_in_schema=False)
def member_badge_submit(token: str, request: Request, full_name: str = Form(...), email: str = Form(...), organization_name: str = Form(''), category: str = Form(...), photo_data: str = Form(...), db: Session = Depends(get_db)):
    event=db.query(Event).filter_by(member_badge_token=token).first()
    if not event: raise HTTPException(404,'Ce lien de badge membre est introuvable ou désactivé.')
    config=json.loads(event.member_badge_config or '{}'); categories=config.get('categories',[])
    if category not in categories: raise HTTPException(422,'Choisissez une catégorie proposée par l’organisateur.')
    if len(photo_data) > 14_000_000: raise HTTPException(413,'La photo est trop volumineuse. Choisissez une image de moins de 10 Mo.')
    photo = process_photo(photo_data)
    if not photo: raise HTTPException(422,'Ajoutez une photo valide (JPEG, PNG ou WebP).')
    email=email.strip().lower()
    if db.query(MemberBadge.id).filter_by(event_id=event.id,email=email).first(): raise HTTPException(409,'Un badge existe déjà pour cette adresse e-mail. Contactez l’organisateur pour le modifier.')
    badge=MemberBadge(event_id=event.id,full_name=full_name.strip(),email=email,organization_name=organization_name.strip(),category=category,photo_data=photo,public_token=secrets.token_urlsafe(32))
    db.add(badge)
    try: db.commit()
    except Exception:
        db.rollback(); raise HTTPException(409,'Un badge vient d’être créé avec cette adresse. Actualisez la page pour le retrouver.')
    return request.app.state.templates.TemplateResponse(request=request,name='member_badge.html',context={'event':event,'categories':categories,'badge':badge,'palette':config.get('palette','royal')})

@router.get('/api/public/member-badge/{public_token}.png', include_in_schema=False)
def member_badge_png(public_token: str, db: Session = Depends(get_db)):
    from app.services.badge import generate_member_badge_png
    badge=db.query(MemberBadge).filter_by(public_token=public_token).first()
    if not badge: raise HTTPException(404,'Badge introuvable.')
    event=db.query(Event).filter_by(id=badge.event_id).first(); config=json.loads(event.member_badge_config or '{}')
    data=generate_member_badge_png(badge,event,config)
    return StreamingResponse(BytesIO(data),media_type='image/png',headers={'Content-Disposition':f'attachment; filename="badge-membre-{badge.id}.png"'})

@router.get('/conference/{registration_token}', response_class=HTMLResponse, include_in_schema=False)
def conference_registration_page(registration_token:str,request:Request,db:Session=Depends(get_db)):
    event=db.query(Event).filter_by(registration_token=registration_token,event_type='conference').first()
    if not event: raise HTTPException(404,'Conférence introuvable.')
    subtitle=' · '.join(x for x in [event.event_date or '',event.venue or ''] if x)
    if not event.registration_open or not organization_accepts_public_activity(db,event.organization_id): return _page(request,mode='closed',title=event.name,subtitle=subtitle,status_code=403)
    schedule=db.query(EventProgramItem).filter_by(event_id=event.id).order_by(EventProgramItem.starts_at).all()
    # Le compteur de capacité et les places restantes ne sont JAMAIS exposés au public (Exigence 4)
    return _page(request,mode='register',title=event.name,subtitle=subtitle,token=registration_token,program=schedule,places=None)


@router.get('/conference/registration/{public_token}', response_class=HTMLResponse, include_in_schema=False)
def conference_manage_page(public_token:str,request:Request,db:Session=Depends(get_db)):
    reg=db.query(ConferenceRegistration).filter_by(public_token=public_token).first()
    if not reg: raise HTTPException(404,'Inscription introuvable.')
    event=db.query(Event).filter_by(id=reg.event_id).first(); label,cls=REG_LABELS.get(reg.status,(reg.status,''))
    return _page(request,mode='manage',title='Mon badge d’accès',subtitle=event.name if event else '',reg=reg,event=event,status_label=label,status_class=cls)


@router.get('/conference/verify/{token}', response_class=HTMLResponse, include_in_schema=False)
def conference_verify_page(token:str,request:Request,db:Session=Depends(get_db)):
    # GET sans effet de bord : les aperçus de liens et antivirus de messagerie ne consomment pas le jeton.
    try: _peek_verification(token,db)
    except HTTPException as exc: return _page(request,400,mode='verify',title='Confirmation de l’adresse e-mail',ok=False,message=exc.detail)
    return _page(request,mode='verify_confirm',title='Confirmation de l’adresse e-mail',token=token)


@router.post('/conference/verify/{token}', response_class=HTMLResponse, include_in_schema=False)
def conference_verify_submit(token:str,request:Request,db:Session=Depends(get_db)):
    try: out=_verify_email(token,db)
    except HTTPException as exc: return _page(request,400,mode='verify',title='Confirmation de l’adresse e-mail',ok=False,message=exc.detail)
    return _page(request,mode='verify',title='Confirmation de l’adresse e-mail',ok=True,message=out['message'],manage_url=out['manage_url'])


@router.get('/admin/api/events/{event_id}/registration-qr.png')
def registration_qr(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False)
    if event.event_type!='conference' or not event.registration_token: raise HTTPException(409,'Cet événement n’est pas une conférence.')
    url=f"{os.getenv('PUBLIC_BASE_URL','http://localhost:8000')}/conference/{event.registration_token}"
    return StreamingResponse(BytesIO(qr_png(url)),media_type='image/png')


@router.get('/admin/api/events/{event_id}/member-badges/preview.png')
def member_badge_preview(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False)
    from types import SimpleNamespace
    from app.services.badge import generate_member_badge_png
    config=json.loads(event.member_badge_config or '{}')
    categories=config.get('categories') or ['Membre']
    sample=SimpleNamespace(full_name='Aperçu du badge',category=categories[0],organization_name='Votre organisation',
                           photo_data=None,badge_reference='00000000-0000-4000-8000-000000000000')
    png=generate_member_badge_png(sample,event,config)
    return StreamingResponse(BytesIO(png),media_type='image/png',headers={'Cache-Control':'no-store'})


@router.get('/admin/api/events/{event_id}/member-badge-qr.png')
def member_badge_qr(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False)
    if not event.member_badge_token:
        raise HTTPException(409,'Activez d’abord le lien de demande de badge membre.')
    url=f"{public_base_url()}/member-badge/{event.member_badge_token}"
    return StreamingResponse(BytesIO(qr_png(url)),media_type='image/png',headers={'Cache-Control':'no-store'})


@router.patch('/api/public/conferences/registration/{public_token}')
def update_public_registration(public_token:str,payload:RegistrationIn,db:Session=Depends(get_db)):
    """Modification des données personnelles autorisées par le participant déjà inscrit (Exigence 5).
    Ne crée jamais de nouvelle inscription ni de nouveau badge.
    Vérification stricte de l'autorisation via le jeton secret public_token."""
    reg=db.query(ConferenceRegistration).filter_by(public_token=public_token).first()
    if not reg: raise HTTPException(404,'Lien personnel invalide ou non vérifié.')
    
    # Résolution du nom complet et prénom / nom
    if payload.first_name or payload.last_name:
        if payload.first_name: reg.first_name = payload.first_name.strip()
        if payload.last_name: reg.last_name = payload.last_name.strip()
        reg.full_name = f"{reg.first_name} {reg.last_name}".strip()
    elif payload.full_name and payload.full_name.strip():
        reg.full_name = payload.full_name.strip()
        parts = reg.full_name.split(' ', 1)
        reg.first_name = parts[0]
        reg.last_name = parts[1] if len(parts) > 1 else ''

    if payload.phone:
        reg.phone = payload.phone.strip()
    if payload.profession is not None:
        reg.profession = payload.profession.strip()
    if payload.organization_name is not None:
        reg.organization_name = payload.organization_name.strip()
    if payload.photo_data:
        processed = process_photo(payload.photo_data)
        if processed:
            reg.photo_data = processed

    db.commit()
    return {
        'message': 'Vos informations personnelles ont été mises à jour avec succès.',
        'status': reg.status,
        'badge_url': f"/api/public/conferences/badge/{reg.public_token}"
    }


@router.get('/api/public/conferences/{registration_token}/program')
def public_conference_program(registration_token:str,db:Session=Depends(get_db)):
    event=db.query(Event).filter_by(registration_token=registration_token,event_type='conference').first()
    if not event: raise HTTPException(404,'Conférence introuvable.')
    rows=db.query(EventProgramItem).filter_by(event_id=event.id).order_by(EventProgramItem.starts_at).all()
    return [{'title':x.title,'description':x.description,'starts_at':x.starts_at.isoformat(),'ends_at':x.ends_at.isoformat(),'location':x.location,'speaker':x.speaker} for x in rows]


@router.get('/api/public/conferences/{registration_token}')
def public_conference_info(registration_token: str, db: Session = Depends(get_db)):
    """Informations publiques de la conférence. Ne divulgue jamais la capacité ni le compteur de places (Exigence 4)."""
    event=db.query(Event).filter_by(registration_token=registration_token,event_type='conference').first()
    if not event: raise HTTPException(404,'Conférence introuvable.')
    return {'name':event.name,'date':event.event_date,'venue':event.venue,'registration_open':event.registration_open}


@router.patch('/admin/api/events/{event_id}/conference')
def configure_conference(event_id:int,request:Request,capacity:int|None=Body(default=None,ge=1),registration_open:bool=Body(default=True),db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    if event.event_type!='conference': raise HTTPException(409,'Cet événement n’est pas une conférence.')
    accepted=db.query(ConferenceRegistration).filter_by(event_id=event_id,status='accepted').count()
    if capacity is not None and capacity<accepted: raise HTTPException(409,'La capacité ne peut pas être inférieure au nombre d’inscriptions acceptées.')
    event.capacity=capacity; event.registration_open=registration_open
    if not event.registration_token: event.registration_token=secrets.token_urlsafe(32)
    _audit(db,u,event_id,'conference.settings.updated',f'capacity={capacity};open={registration_open}'); db.commit()
    return {'registration_url':f"/api/public/conferences/{event.registration_token}",'registration_token':event.registration_token,'capacity':event.capacity,'registration_open':event.registration_open}


@router.post('/admin/api/events/{event_id}/registrations/manual',status_code=201)
def manual_registration(event_id:int,payload:RegistrationIn,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    if event.event_type!='conference': raise HTTPException(409,'Cet événement n’est pas une conférence.')
    
    first_name = (payload.first_name or '').strip()
    last_name = (payload.last_name or '').strip()
    if not first_name or not last_name:
        if payload.full_name and payload.full_name.strip():
            parts = payload.full_name.strip().split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else parts[0]
    full_name = f"{first_name} {last_name}".strip() or (payload.full_name or '').strip()
    if not full_name:
        raise HTTPException(422, 'Le prénom et le nom sont requis pour ajouter un invité.')

    raw_email = (payload.email or '').strip().lower()
    if raw_email:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw_email):
            raise HTTPException(422, 'Adresse e-mail invalide.')
        email = raw_email
        if db.query(ConferenceRegistration).filter_by(event_id=event_id, email=email).first():
            raise HTTPException(409, 'Cette adresse est déjà inscrite.')
    else:
        email = f"guest_{secrets.token_hex(8)}@conference.local"

    phone = (payload.phone or '').strip()
    profession = (payload.profession or '').strip()
    organization_name = (payload.organization_name or '').strip()
    category = (payload.category or 'invité').strip().lower()
    photo = process_photo(payload.photo_data) if payload.photo_data else None

    reg = ConferenceRegistration(
        event_id=event_id,
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        profession=profession,
        organization_name=organization_name,
        category=category,
        photo_data=photo,
        status='accepted',
        is_manual=True,
        email_verified=True,
        public_token=secrets.token_urlsafe(36),
        badge_token=secrets.token_urlsafe(36)
    )
    db.add(reg)
    db.flush()
    _audit(db, u, event_id, 'conference.registration.manual', f'{full_name} ({category})')
    db.commit()

    for admin_user in db.query(User).filter(User.organization_id == event.organization_id, User.role.in_(['admin', 'superadmin'])).all():
        notify_user(admin_user.id, event.organization_id, 'Participant ajouté manuellement', f'{reg.full_name} — {reg.category}', event.id, 'conference')

    badge_url = f"/api/public/conferences/badge/{reg.public_token}"
    return {
        'id': reg.id,
        'status': reg.status,
        'full_name': reg.full_name,
        'first_name': reg.first_name,
        'last_name': reg.last_name,
        'category': reg.category,
        'profession': reg.profession,
        'organization_name': reg.organization_name,
        'phone': reg.phone,
        'email': reg.email if not reg.email.endswith('@conference.local') else '',
        'badge_token': reg.badge_token,
        'badge_reference': reg.badge_reference,
        'badge_url': badge_url,
        'public_token': reg.public_token,
        'message': 'Participant ajouté et badge généré avec succès.'
    }

# ----------------------- Conférence : inscription publique -----------------------
@router.post('/admin/api/events/{event_id}/registrations/import')
async def import_conference_participants(event_id:int,request:Request,file:UploadFile=File(...),db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    if event.event_type!='conference': raise HTTPException(409,'Cet événement n’est pas une conférence.')
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(413,'Fichier trop volumineux (maximum 10 Mo).')
    try: participants=parse_participant_file(file.filename or '',content)
    except ValueError as exc: raise HTTPException(422,str(exc))
    created=[]; skipped=[]
    for p in participants:
        if db.query(ConferenceRegistration.id).filter_by(event_id=event_id,email=p['email']).first(): skipped.append(p['email']); continue
        reg=ConferenceRegistration(event_id=event_id,full_name=p['full_name'],email=p['email'],phone=p['phone'],organization_name=p['organization_name'],category=p['category'],status='accepted',email_verified=True,public_token=secrets.token_urlsafe(36),badge_token=secrets.token_urlsafe(36))
        db.add(reg); created.append(reg)
    _audit(db,u,event_id,'conference.registrations.imported',f'{len(created)} importés; {len(skipped)} ignorés'); db.commit()
    for admin_user in db.query(User).filter(User.organization_id==event.organization_id,User.role.in_(['admin','superadmin'])).all():
        notify_user(admin_user.id,event.organization_id,'Participants importés',f'{len(created)} participant(s) ajouté(s).',event.id,'conference')
    return {'created':len(created),'skipped_duplicates':skipped}

@router.post('/api/public/conferences/{registration_token}/register', status_code=201)
def public_register(registration_token: str, payload: RegistrationIn, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(registration_token=registration_token, event_type='conference', registration_open=True).first()
    if not event or not organization_accepts_public_activity(db, event.organization_id):
        raise HTTPException(404, 'Les inscriptions à cette conférence ne sont pas ouvertes.')
    
    # Identification
    last_name = (payload.last_name or '').strip()
    first_name = (payload.first_name or '').strip()
    if not last_name or not first_name:
        if payload.full_name and payload.full_name.strip():
            parts = payload.full_name.strip().split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else parts[0]
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        raise HTTPException(422, 'Le nom complet est obligatoire.')

    raw_email = (payload.email or '').strip().lower()
    phone = (payload.phone or '').strip()
    profession = (payload.profession or '').strip()
    organization_name = (payload.organization_name or '').strip()
    photo = process_photo(payload.photo_data) if payload.photo_data else None

    # Parcours 1 : Inscription simplifiée avec photo (badge direct)
    if payload.photo_data:
        if not raw_email:
            email = f"participant_{secrets.token_hex(8)}@conference.local"
        else:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw_email):
                raise HTTPException(422, 'Une adresse e-mail valide est requise.')
            email = raw_email
            existing = db.query(ConferenceRegistration).filter_by(event_id=event.id, email=email).first()
            if existing:
                raise HTTPException(
                    409,
                    "Cette adresse e-mail est déjà inscrite à cet événement. La création d'un second badge est refusée. "
                    "Si vous souhaitez modifier vos informations, utilisez votre lien personnel d'accès."
                )

        accepted, capacity = _capacity_state(db, event)
        status = 'waitlist' if (capacity is not None and accepted >= capacity) else 'accepted'
        reg = ConferenceRegistration(
            event_id=event.id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            profession=profession,
            organization_name=organization_name,
            category=payload.category.strip() if payload.category else 'participant',
            photo_data=photo,
            status=status,
            email_verified=True,
            public_token=secrets.token_urlsafe(36),
            badge_token=secrets.token_urlsafe(36)
        )
        db.add(reg)
        db.commit()

        for admin_user in db.query(User).filter(User.organization_id == event.organization_id, User.role.in_(['admin', 'superadmin'])).all():
            notify_user(admin_user.id, event.organization_id, 'Nouvelle inscription conférence', f'{reg.full_name} — {event.name}', event.id, 'conference')

        badge_url = f"/api/public/conferences/badge/{reg.public_token}" if reg.status == 'accepted' else None
        return {
            'message': 'Inscription validée ! Votre badge est prêt à être téléchargé.' if reg.status == 'accepted' else 'Inscription enregistrée sur liste d’attente.',
            'status': reg.status,
            'public_token': reg.public_token,
            'badge_url': badge_url,
            'email_verified': True,
            'registration': {
                'id': reg.id,
                'full_name': reg.full_name,
                'first_name': reg.first_name,
                'last_name': reg.last_name,
                'profession': reg.profession,
                'organization_name': reg.organization_name,
                'event_name': event.name,
                'event_date': event.event_date or '',
                'venue': event.venue or '',
                'badge_token': reg.badge_token,
                'badge_reference': reg.badge_reference,
                'has_photo': bool(reg.photo_data),
                'photo_data': reg.photo_data,
                'badge_url': badge_url
            }
        }

    # Parcours 2 : Inscription publique standard (avec confirmation email anti-énumération)
    if not raw_email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw_email):
        raise HTTPException(422, 'Une adresse e-mail valide est obligatoire.')
    email = raw_email

    existing = db.query(ConferenceRegistration).filter_by(event_id=event.id, email=email).first()
    if existing:
        return {
            'message': 'Si une inscription existe déjà pour cette adresse, contactez l’organisateur pour retrouver votre dossier.',
            'registration_url': None,
        }

    reg = ConferenceRegistration(
        event_id=event.id,
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        profession=profession,
        organization_name=organization_name,
        category=payload.category.strip() if payload.category else 'participant',
        photo_data=None,
        status='pending',
        email_verified=False,
        public_token=secrets.token_urlsafe(36),
        badge_token=secrets.token_urlsafe(36)
    )
    db.add(reg)
    db.flush()

    db.commit()

    for admin_user in db.query(User).filter(User.organization_id == event.organization_id, User.role.in_(['admin', 'superadmin'])).all():
        notify_user(admin_user.id, event.organization_id, 'Nouvelle inscription conférence', f'{reg.full_name} — {reg.email}', event.id, 'conference')

    return {
        'message': 'Demande enregistrée en attente de validation par l’organisateur. Conservez le lien de suivi : il ne sera pas envoyé par e-mail.',
        'status': reg.status,
        'registration_url': f"{public_base_url()}/conference/registration/{reg.public_token}",
    }


def _peek_verification(token: str, db: Session):
    digest=sha256(token.encode()).hexdigest(); row=db.query(EmailVerification).filter_by(token_hash=digest,used_at=None).first()
    if not row or row.expires_at.replace(tzinfo=row.expires_at.tzinfo or timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400,'Lien de vérification invalide ou expiré.')
    return row

def _verify_email(token: str, db: Session):
    row=_peek_verification(token,db)
    reg=db.query(ConferenceRegistration).filter_by(id=row.registration_id).first()
    row.used_at=datetime.now(timezone.utc); reg.email_verified=True  # le statut de modération (accepté, refusé, liste d'attente) n'est jamais écrasé
    db.commit()
    return {'message':'Adresse e-mail vérifiée. Votre inscription attend la validation de l’organisateur.' if reg.status=='pending' else 'Adresse e-mail vérifiée.', 'status':reg.status, 'manage_url':f"/conference/registration/{reg.public_token}"}


@router.post('/api/public/conferences/verify/{token}')
def verify_registration_email(token: str, db: Session = Depends(get_db)):
    return _verify_email(token,db)


@router.get('/api/public/conferences/registration/{public_token}')
def public_registration_detail(public_token: str, db: Session=Depends(get_db)):
    reg=db.query(ConferenceRegistration).filter_by(public_token=public_token).first()
    if not reg: raise HTTPException(404,'Inscription introuvable.')
    event=db.query(Event).filter_by(id=reg.event_id).first()
    return {
        'id': reg.id,
        'full_name': reg.full_name,
        'email': reg.email,
        'phone': reg.phone,
        'organization_name': reg.organization_name,
        'category': reg.category,
        'status': reg.status,
        'email_verified': reg.email_verified,
        'event_id': reg.event_id,
        'event_name': event.name if event else '',
        'event_date': event.event_date if event else '',
        'venue': event.venue if event else '',
        'photo_data': reg.photo_data,
        'badge_token': reg.badge_token,
        'badge_reference': reg.badge_reference,
        'badge_url': f"/api/public/conferences/badge/{reg.public_token}" if reg.status=='accepted' else None
    }


@router.get('/api/public/conferences/badge-qr/{public_token}.png')
def public_badge_qr(public_token: str, db: Session = Depends(get_db)):
    reg = db.query(ConferenceRegistration).filter_by(public_token=public_token).first()
    if not reg or reg.status != 'accepted':
        raise HTTPException(404, 'Badge introuvable ou inscription non acceptée.')
    event = db.query(Event).filter_by(id=reg.event_id).first()
    if not event:
        raise HTTPException(404, 'Événement introuvable.')
    return StreamingResponse(BytesIO(qr_png(build_payload(event.id, reg.badge_reference))), media_type='image/png')


@router.get('/api/public/conferences/badge/{public_token}')
@router.get('/api/public/conferences/badge/{public_token}.png')
def public_badge(public_token: str, db: Session=Depends(get_db)):
    """Génération du badge participant haute fidélité au format PNG (Exigence 1).
    Design professionnel, composition graphique émeraude/malachite, photographie intégrée,
    QR code scannable, prêt pour impression et téléchargement."""
    reg=db.query(ConferenceRegistration).filter_by(public_token=public_token).first()
    if not reg or reg.status!='accepted':
        raise HTTPException(403,'Badge disponible uniquement après acceptation de votre inscription.')
    event=db.query(Event).filter_by(id=reg.event_id).first()
    if not event:
        raise HTTPException(404,'Événement introuvable.')
    
    png_bytes = generate_participant_badge_png(reg, event)
    return StreamingResponse(
        BytesIO(png_bytes),
        media_type='image/png',
        headers={'Content-Disposition': f'attachment; filename="badge_{reg.id}.png"'}
    )


@router.get('/admin/api/events/{event_id}/registrations')
def list_registrations(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u,write=False)
    rows=db.query(ConferenceRegistration).filter_by(event_id=event_id).order_by(ConferenceRegistration.created_at).all()
    accepted,capacity=_capacity_state(db,event)
    return {'capacity':capacity,'accepted_count':accepted,'registrations':[{'id':r.id,'name':r.full_name,'email':r.email,'category':r.category,'status':r.status,'verified':r.email_verified,'created_at':r.created_at.isoformat()} for r in rows]}


@router.patch('/admin/api/events/{event_id}/registrations/{registration_id}')
def moderate_registration(event_id:int,registration_id:int,payload:RegistrationStatus,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    reg=db.query(ConferenceRegistration).filter_by(id=registration_id,event_id=event_id).first()
    if not reg: raise HTTPException(404,'Inscription introuvable.')
    accepted,capacity=_capacity_state(db,event)
    try: target_status=decide_registration_status(payload.status,event.capacity,accepted,reg.status=='accepted')
    except ValueError as exc: raise HTTPException(409,str(exc))
    previous=reg.status; reg.status=target_status
    db.flush()  # SessionLocal disables autoflush; release the accepted seat before counting capacity.
    promoted=[]
    if previous=='accepted' and target_status!='accepted': promoted=_promote_waitlist(db,event)
    _audit(db,u,event_id,'conference.registration.status',f'{reg.id}: {previous} -> {reg.status}')
    db.commit()
    return {'id':reg.id,'status':reg.status}


@router.patch('/admin/api/events/{event_id}/registrations/{registration_id}/details')
def update_registration_details(event_id:int,registration_id:int,payload:AdminRegistrationUpdate,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    reg=db.query(ConferenceRegistration).filter_by(id=registration_id,event_id=event_id).first()
    if not reg: raise HTTPException(404,'Inscription introuvable.')

    if payload.first_name is not None: reg.first_name = payload.first_name.strip()
    if payload.last_name is not None: reg.last_name = payload.last_name.strip()
    if payload.full_name is not None and payload.full_name.strip():
        reg.full_name = payload.full_name.strip()
    elif reg.first_name or reg.last_name:
        reg.full_name = f"{reg.first_name} {reg.last_name}".strip()

    if payload.email is not None and payload.email.strip():
        clean_email = payload.email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean_email):
            raise HTTPException(422, 'Adresse e-mail invalide.')
        dup = db.query(ConferenceRegistration).filter(ConferenceRegistration.event_id == event_id, ConferenceRegistration.email == clean_email, ConferenceRegistration.id != reg.id).first()
        if dup: raise HTTPException(409, 'Cette adresse e-mail est déjà utilisée par un autre participant.')
        reg.email = clean_email

    if payload.phone is not None: reg.phone = payload.phone.strip()
    if payload.profession is not None: reg.profession = payload.profession.strip()
    if payload.organization_name is not None: reg.organization_name = payload.organization_name.strip()
    if payload.category is not None and payload.category.strip(): reg.category = payload.category.strip().lower()
    if payload.photo_data is not None:
        reg.photo_data = process_photo(payload.photo_data) if payload.photo_data.strip() else None

    if payload.regenerate_qr:
        reg.badge_token = secrets.token_urlsafe(36)
        reg.badge_reference = new_badge_reference()

    _audit(db, u, event_id, 'conference.registration.updated', f'{reg.id}: {reg.full_name}')
    db.commit()
    return {
        'id': reg.id,
        'full_name': reg.full_name,
        'first_name': reg.first_name,
        'last_name': reg.last_name,
        'email': reg.email if not reg.email.endswith('@conference.local') else '',
        'phone': reg.phone,
        'profession': reg.profession,
        'organization_name': reg.organization_name,
        'category': reg.category,
        'badge_token': reg.badge_token,
        'badge_reference': reg.badge_reference,
        'badge_url': f"/api/public/conferences/badge/{reg.public_token}",
        'message': 'Informations du participant mises à jour avec succès.'
    }


@router.post('/admin/api/events/{event_id}/registrations/{registration_id}/regenerate-qr')
def regenerate_registration_qr(event_id:int,registration_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    reg=db.query(ConferenceRegistration).filter_by(id=registration_id,event_id=event_id).first()
    if not reg: raise HTTPException(404,'Inscription introuvable.')
    old_token = reg.badge_token
    reg.badge_token = secrets.token_urlsafe(36)
    reg.badge_reference = new_badge_reference()
    _audit(db, u, event_id, 'conference.registration.qr_regenerated', f'{reg.id}: ancien token révoqué')
    db.commit()
    return {
        'id': reg.id,
        'badge_token': reg.badge_token,
        'badge_reference': reg.badge_reference,
        'badge_url': f"/api/public/conferences/badge/{reg.public_token}",
        'message': 'Nouveau QR code généré. L’ancien badge est désormais révoqué et inutilisable.'
    }

# ----------------------- Contrôle des badges conférence -----------------------
@router.post('/checkin/api/conferences/{event_id}/scan')
def scan_conference_badge(event_id:int,request:Request,payload:ConferenceScanIn,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); event=ensure_event_organization(db,event_id,u)
    if event.event_type!='conference': raise HTTPException(409,'Cet événement n’est pas une conférence.')
    if event.status!='active': raise HTTPException(409,'Événement non actif : activez-le (état « En cours ») avant de contrôler les badges.')
    if u['role'] not in {'admin','superadmin'} and not db.query(EventAssignment).filter_by(event_id=event_id,user_id=u['id']).first(): raise HTTPException(403,'Vous n’êtes pas affecté à cette conférence.')
    
    reference = (payload.badge_reference or '').strip()
    legacy_token = (payload.badge_token or '').strip()
    reg_id = payload.registration_id
    idem = payload.idempotency_key

    if reference and legacy_token:
        raise HTTPException(422, 'Fournissez soit la référence UUID du badge, soit un ancien jeton, pas les deux.')
    if reference:
        if not is_uuid4(reference):
            raise HTTPException(422, 'Référence de badge UUID v4 invalide.')
        reg = db.query(ConferenceRegistration).filter_by(
            event_id=event_id, badge_reference=reference.lower()
        ).with_for_update().first()
    elif legacy_token:
        token = legacy_token
        if token.startswith('BADGE:'):
            match = re.fullmatch(r'BADGE:([0-9a-fA-F-]{36})', token, re.IGNORECASE)
            if not match or not is_uuid4(match.group(1)):
                raise HTTPException(422, 'QR de badge UUID v4 invalide.')
            token = match.group(1).lower()
            reg = db.query(ConferenceRegistration).filter_by(
                event_id=event_id, badge_reference=token
            ).with_for_update().first()
        elif token.startswith('CONF:') or token.startswith('IA1.'):
            match = (re.fullmatch(r'CONF:(\d+):([A-Za-z0-9_-]{20,128})', token)
                     if token.startswith('CONF:') else re.fullmatch(r'IA1\.(\d{1,9})\.([A-Za-z0-9_-]{16,128})', token))
            if not match:
                raise HTTPException(422, 'QR de badge invalide.')
            if int(match.group(1)) != event_id:
                raise HTTPException(404, 'Badge ou participant introuvable pour cette conférence.')
            token = match.group(2)
            if looks_like_uuid(token) and not is_uuid4(token):
                raise HTTPException(422, 'Référence de badge UUID invalide.')
        if looks_like_uuid(token) and not is_uuid4(token):
            raise HTTPException(422, 'Référence de badge UUID invalide.')
            if is_uuid4(token):
                reg = db.query(ConferenceRegistration).filter_by(
                    event_id=event_id, badge_reference=token.lower()
                ).with_for_update().first()
            else:
                reg = db.query(ConferenceRegistration).filter_by(
                    event_id=event_id, badge_token=token
                ).with_for_update().first()
        elif looks_like_uuid(token):
            if not is_uuid4(token):
                raise HTTPException(422, 'Référence de badge UUID v4 invalide.')
            reg = db.query(ConferenceRegistration).filter_by(
                event_id=event_id, badge_reference=token.lower()
            ).with_for_update().first()
        else:
            reg = db.query(ConferenceRegistration).filter_by(
                event_id=event_id, badge_token=token
            ).with_for_update().first()
    elif reg_id:
        reg = db.query(ConferenceRegistration).filter_by(event_id=event_id, id=reg_id).with_for_update().first()
    else:
        raise HTTPException(422, 'Jeton de badge ou identifiant de participant requis.')

    if not reg:
        raise HTTPException(404, 'Badge ou participant introuvable pour cette conférence.')
    if reg.status != 'accepted':
        raise HTTPException(403, f'Accès refusé : inscription non acceptée (statut : {reg.status}).')

    if idem:
        prior_idem = db.query(ConferenceCheckin).filter_by(event_id=event_id, idempotency_key=idem).first()
        if prior_idem:
            if prior_idem.registration_id != reg.id:
                raise HTTPException(409, 'Clé idempotente déjà utilisée pour un autre badge.')
            return {
                'status': 'already_checked_in',
                'registration_id': reg.id,
                'name': reg.full_name,
                'first_name': reg.first_name,
                'last_name': reg.last_name,
                'category': reg.category,
                'profession': reg.profession,
                'organization_name': reg.organization_name,
                'photo_data': reg.photo_data,
                'checked_in_at': prior_idem.checked_in_at.isoformat(),
                'already_registered': True,
                'message': f"Ce participant a déjà été validé à {prior_idem.checked_in_at.strftime('%H:%M:%S')}."
            }

    prior = db.query(ConferenceCheckin).filter_by(registration_id=reg.id).first()
    if prior:
        return {
            'status': 'already_checked_in',
            'registration_id': reg.id,
            'name': reg.full_name,
            'first_name': reg.first_name,
            'last_name': reg.last_name,
            'category': reg.category,
            'profession': reg.profession,
            'organization_name': reg.organization_name,
            'photo_data': reg.photo_data,
            'checked_in_at': prior.checked_in_at.isoformat(),
            'event_name': event.name,
            'message': f"Ce participant a déjà été validé à {prior.checked_in_at.strftime('%H:%M:%S')}."
        }

    rec = ConferenceCheckin(event_id=event_id, registration_id=reg.id, user_id=u['id'], idempotency_key=idem)
    db.add(rec)
    _audit(db, u, event_id, 'conference.badge.checked_in', f'registration={reg.id}; method={payload.method}')
    try:
        db.commit()
    except Exception:
        db.rollback()
        prior = db.query(ConferenceCheckin).filter_by(registration_id=reg.id).first()
        if prior:
            return {
                'status': 'already_checked_in',
                'registration_id': reg.id,
                'name': reg.full_name,
                'first_name': reg.first_name,
                'last_name': reg.last_name,
                'category': reg.category,
                'checked_in_at': prior.checked_in_at.isoformat(),
                'event_name': event.name
            }
        raise

    return {
        'status': 'checked_in',
        'registration_id': reg.id,
        'name': reg.full_name,
        'first_name': reg.first_name,
        'last_name': reg.last_name,
        'category': reg.category,
        'profession': reg.profession,
        'organization_name': reg.organization_name,
        'photo_data': reg.photo_data,
        'checked_in_at': rec.checked_in_at.isoformat(),
        'event_name': event.name,
        'message': 'Entrée validée avec succès.'
    }

# ----------------------- Programme -----------------------
@router.get('/api/events/{event_id}/program')
def get_program(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); event=ensure_event_organization(db,event_id,u); _ensure_assigned(db,event_id,u)
    rows=db.query(EventProgramItem).filter_by(event_id=event_id).order_by(EventProgramItem.starts_at,EventProgramItem.sort_order).all()
    return [{'id':x.id,'title':x.title,'description':x.description,'starts_at':x.starts_at.isoformat(),'ends_at':x.ends_at.isoformat(),'location':x.location,'speaker':x.speaker} for x in rows]


@router.post('/admin/api/events/{event_id}/program',status_code=201)
def add_program(event_id:int,payload:ProgramIn,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u)
    if payload.ends_at<=payload.starts_at: raise HTTPException(422,'L’heure de fin doit suivre l’heure de début.')
    item=EventProgramItem(event_id=event_id,title=payload.title,description=payload.description,starts_at=payload.starts_at,ends_at=payload.ends_at,location=payload.location,speaker=payload.speaker,created_by=u['id'])
    db.add(item); _audit(db,u,event_id,'program.created',item.title); db.commit(); _notify_event_team(db,event,'Programme mis à jour',item.title,'program'); return {'id':item.id}


@router.put('/admin/api/events/{event_id}/program/{item_id}')
def edit_program(event_id:int,item_id:int,payload:ProgramIn,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u); item=db.query(EventProgramItem).filter_by(id=item_id,event_id=event_id).first()
    if not item: raise HTTPException(404,'Séquence introuvable.')
    if payload.ends_at<=payload.starts_at: raise HTTPException(422,'L’heure de fin doit suivre le début.')
    item.title=payload.title; item.description=payload.description; item.starts_at=payload.starts_at; item.ends_at=payload.ends_at; item.location=payload.location; item.speaker=payload.speaker
    _audit(db,u,event_id,'program.updated',item.title); db.commit(); _notify_event_team(db,event,'Programme modifié',item.title,'program'); return {'message':'Programme modifié.'}


@router.delete('/admin/api/events/{event_id}/program/{item_id}')
def delete_program(event_id:int,item_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin'); event=_admin_event(db,event_id,u); item=db.query(EventProgramItem).filter_by(id=item_id,event_id=event_id).first()
    if not item: raise HTTPException(404,'Séquence introuvable.')
    title=item.title; _audit(db,u,event_id,'program.deleted',title); db.delete(item); db.commit(); _notify_event_team(db,event,'Programme modifié',title,'program'); return {'message':'Séquence supprimée.'}


@router.get('/api/events/{event_id}/program.pdf')
def export_program(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); event=ensure_event_organization(db,event_id,u); _ensure_assigned(db,event_id,u)
    rows=db.query(EventProgramItem).filter_by(event_id=event_id).order_by(EventProgramItem.starts_at).all()
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4); styles=getSampleStyleSheet()
    story=[Paragraph(f'Programme — {pdf_text(event.name)}',styles['Title']),Spacer(1,8*mm)]
    data=[['Horaire','Activité','Lieu','Intervenant']]
    for x in rows: data.append([f'{x.starts_at:%d/%m %H:%M} – {x.ends_at:%H:%M}',x.title,x.location or '—',x.speaker or '—'])
    table=Table(data,colWidths=[42*mm,70*mm,38*mm,38*mm],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17324D')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.4,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(table); doc.build(story); buf.seek(0)
    return StreamingResponse(buf,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="programme_{event_id}.pdf"'})

# ----------------------- Tâches / responsabilités -----------------------
@router.get('/api/events/{event_id}/tasks')
def list_tasks(event_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); ensure_event_organization(db,event_id,u); _ensure_assigned(db,event_id,u)
    rows=db.query(TeamTask).filter_by(event_id=event_id).order_by(TeamTask.due_at,TeamTask.id).all()
    if u['role'] not in ('admin','superadmin','supervisor'): rows=[t for t in rows if t.assigned_to==u['id']]
    return [{'id':t.id,'title':t.title,'description':t.description,'assigned_to':t.assigned_to,'status':t.status,'priority':t.priority,'due_at':t.due_at.isoformat() if t.due_at else None} for t in rows]


@router.post('/admin/api/events/{event_id}/tasks',status_code=201)
def create_task(event_id:int,payload:TaskIn,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor'); event=ensure_event_organization(db,event_id,u); _ensure_assigned(db,event_id,u); ensure_can_write(db,u,event.organization_id)
    if payload.assigned_to:
        target=db.query(User).filter_by(id=payload.assigned_to,organization_id=event.organization_id,active=True).first()
        if not target: raise HTTPException(422,'Utilisateur affecté invalide.')
        if not db.query(EventAssignment).filter_by(event_id=event_id,user_id=target.id).first(): raise HTTPException(422,'Affectez d’abord cet utilisateur à l’équipe de l’événement.')
    task=TeamTask(event_id=event_id,title=payload.title,description=payload.description,assigned_to=payload.assigned_to,status=payload.status,priority=payload.priority,due_at=payload.due_at,created_by=u['id'])
    db.add(task); db.flush(); db.add(TaskHistory(task_id=task.id,user_id=u['id'],action='created',new_value=payload.model_dump_json()));
    _audit(db,u,event_id,'task.created',task.title); db.commit();
    if payload.assigned_to: notify_user(payload.assigned_to,event.organization_id,'Nouvelle responsabilité',task.title,event_id,'task')
    return {'id':task.id}


@router.patch('/api/events/{event_id}/tasks/{task_id}')
def update_task(event_id:int,task_id:int,payload:TaskIn,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); event=ensure_event_organization(db,event_id,u); _ensure_assigned(db,event_id,u); ensure_can_write(db,u,event.organization_id)
    task=db.query(TeamTask).filter_by(id=task_id,event_id=event_id).first()
    if not task: raise HTTPException(404,'Tâche introuvable.')
    if u['role']=='agent' and task.assigned_to!=u['id']: raise HTTPException(403,'Vous ne pouvez modifier que vos propres tâches.')
    if u['role']=='agent' and (payload.title!=task.title or payload.description!=task.description or payload.assigned_to!=task.assigned_to or payload.priority!=task.priority or payload.due_at!=task.due_at): raise HTTPException(403,'Un agent peut uniquement mettre à jour le statut de sa tâche.')
    if payload.assigned_to:
        target=db.query(User).filter_by(id=payload.assigned_to,organization_id=event.organization_id,active=True).first()
        if not target: raise HTTPException(422,'Utilisateur affecté invalide.')
        if not db.query(EventAssignment).filter_by(event_id=event_id,user_id=target.id).first(): raise HTTPException(422,'Affectez d’abord cet utilisateur à l’équipe de l’événement.')
    old=payload.model_dump(); before={'title':task.title,'description':task.description,'assigned_to':task.assigned_to,'status':task.status,'priority':task.priority,'due_at':task.due_at.isoformat() if task.due_at else None}
    for key,val in old.items(): setattr(task,key,val)
    db.add(TaskHistory(task_id=task.id,user_id=u['id'],action='updated',old_value=str(before),new_value=str(old)))
    _audit(db,u,event_id,'task.updated',task.title); db.commit();
    if before['assigned_to']!=task.assigned_to and task.assigned_to: notify_user(task.assigned_to,event.organization_id,'Responsabilité attribuée',task.title,event_id,'task')
    return {'message':'Tâche mise à jour.'}


@router.get('/api/events/{event_id}/tasks/{task_id}/history')
def task_history(event_id:int,task_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); ensure_event_organization(db,event_id,u); _ensure_assigned(db,event_id,u)
    task=db.query(TeamTask).filter_by(id=task_id,event_id=event_id).first()
    if not task: raise HTTPException(404,'Tâche introuvable.')
    if u['role']=='agent' and task.assigned_to!=u['id']: raise HTTPException(403,'Accès refusé.')
    rows=db.query(TaskHistory,User).join(User,User.id==TaskHistory.user_id).filter(TaskHistory.task_id==task_id).order_by(TaskHistory.created_at.desc()).all()
    return [{'user':usr.full_name,'action':h.action,'old_value':h.old_value,'new_value':h.new_value,'created_at':h.created_at.isoformat()} for h,usr in rows]

# ----------------------- Notifications / Push -----------------------
@router.get('/api/notifications')
def my_notifications(request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent')
    rows=db.query(Notification).filter_by(user_id=u['id']).order_by(Notification.created_at.desc()).limit(100).all()
    return [{'id':n.id,'title':n.title,'body':n.body,'category':n.category,'event_id':n.event_id,'read':n.read_at is not None,'created_at':n.created_at.isoformat()} for n in rows]


@router.post('/api/notifications/{notification_id}/read')
def mark_notification_read(notification_id:int,request:Request,db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); n=db.query(Notification).filter_by(id=notification_id,user_id=u['id']).first()
    if not n: raise HTTPException(404,'Notification introuvable.')
    n.read_at=datetime.now(timezone.utc); db.commit(); return {'message':'Notification marquée comme lue.'}


@router.get('/api/push/public-key')
def push_public_key():
    key=get_vapid_public_key()
    if not key: raise HTTPException(503,'Notifications push non configurées ou clé invalide.')
    return {'public_key':key}


@router.post('/api/push/subscribe')
def push_subscribe(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); endpoint=payload.get('endpoint'); keys=payload.get('keys') or {}
    if not get_vapid_public_key(): raise HTTPException(503,'Notifications push non configurées ou clé invalide.')
    if (not isinstance(endpoint,str) or not endpoint.startswith('https://') or len(endpoint)>2048 or
        not isinstance(keys,dict) or not isinstance(keys.get('p256dh'),str) or not isinstance(keys.get('auth'),str) or
        not 16<=len(keys['p256dh'])<=255 or not 16<=len(keys['auth'])<=255):
        raise HTTPException(422,'Abonnement push invalide.')
    existing=db.query(PushSubscription).filter_by(endpoint=endpoint).first()
    if existing:
        if existing.user_id!=u['id']: raise HTTPException(409,'Cet appareil est déjà associé à un autre compte.')
        existing.p256dh=keys['p256dh']; existing.auth=keys['auth']
    else: db.add(PushSubscription(user_id=u['id'],endpoint=endpoint,p256dh=keys['p256dh'],auth=keys['auth']))
    db.commit(); return {'message':'Appareil enregistré pour les notifications push.'}


@router.delete('/api/push/subscribe')
def push_unsubscribe(request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    u=require_roles(request,'admin','superadmin','supervisor','agent'); endpoint=payload.get('endpoint')
    if not isinstance(endpoint,str) or not endpoint.startswith('https://') or len(endpoint)>2048:
        raise HTTPException(422,'Abonnement push invalide.')
    subscription = db.query(PushSubscription).filter_by(user_id=u['id'], endpoint=endpoint).first()
    if subscription:
        db.query(PushOutbox).filter_by(subscription_id=subscription.id).delete(synchronize_session=False)
        db.delete(subscription)
    db.commit()
    return {'message':'Abonnement push supprimé.'}

