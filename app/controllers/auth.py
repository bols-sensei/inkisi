from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Organization, AuditLog
from app.security import (verify_password, current_user, create_access_token, hash_password, login_session, revoke_sessions)
from app.schemas import TokenRequest, OrganizationCreate, PasswordChange
from app.services import accounts
from app.services.ratelimit import client_ip, login_blocked, login_failed
from app.services.organizations import create_organization_with_admin

router = APIRouter()


def _org_suspended(db: Session, user: User) -> bool:
    if user.role == 'superadmin' or not user.organization_id:
        return False
    org = db.query(Organization).filter_by(id=user.organization_id).first()
    return not org or org.status != 'active'


def _login_error(request: Request, message: str, status: int = 401):
    return request.app.state.templates.TemplateResponse(request=request, name='login.html', context={'error': message}, status_code=status)


def _page(request: Request, status: int = 200, **ctx):
    base = {'title': '', 'message': '', 'kind': 'ok', 'form': None, 'link': None}
    return request.app.state.templates.TemplateResponse(request=request, name='account_message.html', context={**base, **ctx}, status_code=status)


@router.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    ip = client_ip(request)
    if login_blocked(username, ip):
        return _login_error(request, 'Trop de tentatives échouées. Réessayez dans quelques minutes.', 429)
    user = db.query(User).filter(func.lower(User.username) == username.strip().lower(), User.active == True).first()
    if not user or not verify_password(password, user.password_hash):
        login_failed(username, ip)
        return _login_error(request, 'Identifiants incorrects ou compte désactivé.')
    if _org_suspended(db, user):
        return _login_error(request, 'Votre organisation est suspendue. Contactez le support de la plateforme.', 403)
    login_session(request, user)
    return RedirectResponse('/', status_code=303)


@router.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/', status_code=303)


@router.get('/api/me')
def me(request: Request):
    return current_user(request)


@router.post('/api/auth/token')
def issue_token(request: Request, payload: TokenRequest, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if login_blocked(payload.username, ip):
        raise HTTPException(status_code=429, detail='Trop de tentatives échouées. Réessayez dans quelques minutes.')
    user = db.query(User).filter(func.lower(User.username) == payload.username.strip().lower(), User.active == True).first()
    if not user or not verify_password(payload.password, user.password_hash):
        login_failed(payload.username, ip)
        raise HTTPException(status_code=401, detail='Identifiants incorrects ou compte désactivé.', headers={'WWW-Authenticate': 'Bearer'})
    if _org_suspended(db, user):
        raise HTTPException(status_code=403, detail='Organisation suspendue. Contactez le support de la plateforme.')
    info = {'id': user.id, 'username': user.username, 'full_name': user.full_name, 'role': user.role,
            'organization_id': user.organization_id, 'token_version': user.token_version}
    token, expires_in = create_access_token(info)
    return {'access_token': token, 'token_type': 'bearer', 'expires_in': expires_in,
            'user': {'id': user.id, 'username': user.username, 'full_name': user.full_name, 'role': user.role, 'organization_id': user.organization_id}}


@router.post('/api/organizations/register', status_code=201)
def register_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    """Inscription publique : e-mail obligatoire et unique (un essai par adresse), à vérifier avant de créer des événements."""
    org, admin, sub = create_organization_with_admin(
        db, name=payload.name, username=payload.admin_username, full_name=payload.admin_full_name,
        password=payload.admin_password, email=payload.admin_email, email_verified=False, require_email=True)
    db.commit()
    return {'message': 'Organisation créée. Vous pouvez vous connecter immédiatement. L’adresse e-mail fournie sert de contact et ne reçoit pas de message.',
            'organization': {'id': org.id, 'name': org.name, 'slug': org.slug},
            'admin': {'id': admin.id, 'username': admin.username},
            'trial': {'status': 'trial', 'starts_at': sub.starts_at.isoformat(), 'ends_at': sub.ends_at.isoformat()}}


# ---------------- Compte connecté ----------------
@router.post('/api/me/password')
def change_my_password(request: Request, payload: PasswordChange, db: Session = Depends(get_db)):
    me_ = current_user(request)
    user = db.query(User).filter_by(id=me_['id']).first()
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(403, 'Mot de passe actuel incorrect.')
    user.password_hash = hash_password(payload.new_password)
    revoke_sessions(user)  # déconnecte tous les autres appareils et jetons JWT
    db.add(AuditLog(user_id=user.id, event_id=None, action='user.password_changed', details=user.username))
    db.commit()
    if not request.headers.get('Authorization'):
        request.session['tv'] = user.token_version  # garde la session courante valide
    return {'message': 'Mot de passe modifié. Les autres appareils ont été déconnectés.'}


# ---------------- Pages : vérification d'adresse et mot de passe oublié ----------------
@router.get('/verify-account/{token}', include_in_schema=False)
def verify_account_page(token: str, request: Request, db: Session = Depends(get_db)):
    # GET sans effet de bord : les aperçus de liens et antivirus de messagerie ne consomment pas le jeton.
    if not accounts.peek_token(db, token, accounts.VERIFY):
        return _page(request, 400, title='Lien invalide', message='Ce lien de confirmation est invalide ou a expiré.', kind='bad', link=('/', 'Retour à la connexion'))
    return _page(request, title='Confirmer mon adresse e-mail', message='Cliquez pour confirmer votre adresse.',
                 form={'action': f'/verify-account/{token}', 'button': 'Confirmer mon adresse', 'fields': []})


@router.post('/verify-account/{token}', include_in_schema=False)
def verify_account(token: str, request: Request, db: Session = Depends(get_db)):
    user = accounts.consume_token(db, token, accounts.VERIFY)
    if not user:
        return _page(request, 400, title='Lien invalide', message='Ce lien de confirmation est invalide ou a expiré.', kind='bad', link=('/', 'Retour à la connexion'))
    user.email_verified = True
    db.commit()
    return _page(request, title='Adresse confirmée', message='Votre adresse e-mail est confirmée. Vous pouvez créer vos événements.', link=('/', 'Aller à l’application'))


@router.get('/forgot-password', include_in_schema=False)
def forgot_password_page(request: Request):
    return _page(request, title='Mot de passe oublié', message='La récupération par e-mail est désactivée. Demandez à l’administrateur de votre organisation de réinitialiser votre mot de passe. Pour un compte plateforme, utilisez le compte superadministrateur de secours configuré par l’exploitant.',
                 link=('/', 'Retour à la connexion'))


@router.post('/forgot-password', include_in_schema=False)
def forgot_password(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    # Ne jamais générer de lien de réinitialisation public sans un canal de livraison vérifié.
    return forgot_password_page(request)


@router.get('/reset-password/{token}', include_in_schema=False)
def reset_password_page(token: str, request: Request, db: Session = Depends(get_db)):
    if not accounts.peek_token(db, token, accounts.RESET):
        return _page(request, 400, title='Lien invalide', message='Ce lien est invalide ou a expiré. Refaites une demande.', kind='bad', link=('/forgot-password', 'Nouvelle demande'))
    return _page(request, title='Nouveau mot de passe', message='Choisissez un mot de passe d’au moins 10 caractères.',
                 form={'action': f'/reset-password/{token}', 'button': 'Enregistrer', 'fields': [{'name': 'new_password', 'label': 'Nouveau mot de passe', 'type': 'password', 'autocomplete': 'new-password', 'minlength': 10}]})


@router.post('/reset-password/{token}', include_in_schema=False)
def reset_password(token: str, request: Request, new_password: str = Form(...), db: Session = Depends(get_db)):
    if len(new_password) < 10 or len(new_password) > 256:
        return _page(request, 422, title='Mot de passe trop court', message='Le mot de passe doit contenir entre 10 et 256 caractères.', kind='bad',
                     form={'action': f'/reset-password/{token}', 'button': 'Enregistrer', 'fields': [{'name': 'new_password', 'label': 'Nouveau mot de passe', 'type': 'password', 'autocomplete': 'new-password', 'minlength': 10}]})
    user = accounts.consume_token(db, token, accounts.RESET)
    if not user:
        return _page(request, 400, title='Lien invalide', message='Ce lien est invalide ou a expiré. Refaites une demande.', kind='bad', link=('/forgot-password', 'Nouvelle demande'))
    user.password_hash = hash_password(new_password)
    revoke_sessions(user)
    db.add(AuditLog(user_id=user.id, event_id=None, action='user.password_reset', details=user.username))
    db.commit()
    return _page(request, title='Mot de passe modifié', message='Votre mot de passe a été changé. Toutes les sessions ouvertes ont été déconnectées.', link=('/', 'Se connecter'))
