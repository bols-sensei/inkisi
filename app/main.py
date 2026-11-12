from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from sqlalchemy import text
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import os
from app.database import Base, engine, SessionLocal
from app.security import optional_user
from app.controllers import auth, admin, supervisor, checkin, superadmin, operations, support

BASE_DIR = Path(__file__).resolve().parent.parent  # FIX: racine du projet, pas le dossier app/.
APP_DIR = BASE_DIR / "app"
# Database schema is managed exclusively by Alembic. Run `alembic upgrade head` before startup.

# Refuse insecure fallback secrets in production.
from app.config import ENVIRONMENT, is_production, validate_production_config
validate_production_config()
@asynccontextmanager
async def lifespan(app):
    from app.services.push_worker import run_worker
    worker = asyncio.create_task(run_worker(), name='push-outbox-worker')
    app.state.push_outbox_worker = worker
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Invitation Access Control", version="0.3.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-only-change-me"), same_site="lax", https_only=is_production(), max_age=int(os.getenv('SESSION_MAX_AGE_SECONDS','43200')))

from app.middleware import RateLimitMiddleware, OriginCheckMiddleware, SecurityHeadersMiddleware
if is_production():
    from app.services.ratelimit import limiter
    try:
        if limiter.redis is None:
            raise RuntimeError('RATE_LIMIT_REDIS_URL ne permet pas d’initialiser le client Redis.')
        limiter.redis.ping()
    except Exception as exc:
        raise RuntimeError('Redis doit être joignable au démarrage en production.') from exc
app.add_middleware(RateLimitMiddleware)
app.add_middleware(OriginCheckMiddleware)
if os.getenv('ALLOWED_HOSTS'):
    _allowed = [x.strip() for x in os.getenv('ALLOWED_HOSTS','').split(',') if x.strip()]
    if not is_production() and 'testserver' not in _allowed:
        _allowed.append('testserver')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed)
app.add_middleware(SecurityHeadersMiddleware)  # ajouté en dernier = le plus externe : couvre aussi les réponses d'erreur des autres middlewares
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "views"))
# FIX: expose templates before any route can use request.app.state.templates.
app.state.templates = templates

# Données de référence + compte plateforme (nécessite `alembic upgrade head`).
from app.bootstrap import init as _init_platform
_init_platform()

@app.get("/", include_in_schema=False)
def home(request: Request):
    user = optional_user(request)  # valide le compte en base : un cookie périmé ne montre plus le tableau de bord
    if user:
        return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user})  # FIX: signature Starlette récente (request, name, context).
    return templates.TemplateResponse(request=request, name="login.html", context={})  # FIX: éviter que le dictionnaire soit interprété comme le nom du template.

# Service worker servi à la racine : sa portée couvre alors « / » et « /event/... » (mode hors ligne).
@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(APP_DIR / "static" / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/event/{event_id}", include_in_schema=False)
def event_page(event_id: int, request: Request):
    user = optional_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="event.html", context={"event_id": event_id, "user": user})  # FIX: signature Starlette récente.

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(supervisor.router)
app.include_router(checkin.router)
app.include_router(superadmin.router)
app.include_router(operations.router)
app.include_router(support.router)
