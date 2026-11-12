from urllib.parse import urlparse
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import is_production, public_base_url
from app.services.ratelimit import limiter, client_ip, LimiterUnavailable

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; media-src 'self' blob:; worker-src 'self' blob:; manifest-src 'self'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limites par IP : routes sensibles (8/min), formulaires publics (30/min), API (1500/min, large pour un lieu
    où plusieurs agents partagent une même IP). Les échecs de connexion sont limités par compte dans les contrôleurs."""
    async def dispatch(self, request, call_next):
        path = request.url.path
        if limiter.disabled(): return await call_next(request)
        special = ('/reset-password/', '/verify-account/', '/conference/verify/')
        if path in {'/login', '/api/auth/token', '/api/organizations/register', '/forgot-password'} or path.endswith('/register') or path.startswith(special):
            limit, window, bucket = 8, 60, path
            for prefix in special:
                if path.startswith(prefix): bucket = prefix.rstrip('/')
        elif path.startswith('/api/public/'):
            limit, window, bucket = 30, 60, path
        elif path.startswith(('/api/', '/admin/api/', '/supervisor/api/', '/superadmin/api/')):
            limit, window, bucket = 1500, 60, 'api'
        else:
            return await call_next(request)
        key = f"{client_ip(request)}:{bucket}"
        try:
            if limiter.record(key, window) > limit:
                return JSONResponse({'detail': 'Trop de requêtes. Réessayez dans une minute.'}, status_code=429, headers={'Retry-After': str(limiter.retry_after(key, window))})
        except LimiterUnavailable:
            if is_production(): return JSONResponse({'detail': 'Service de sécurité temporairement indisponible.'}, status_code=503)
        return await call_next(request)


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Protection CSRF sans jeton : une requête qui modifie l'état doit venir de notre propre origine
    (en-têtes Origin/Referer, puis Sec-Fetch-Site). Les appels avec jeton Bearer ne dépendent pas d'un cookie."""
    SAFE = {'GET', 'HEAD', 'OPTIONS'}

    def _allowed(self, request):
        hosts = {request.headers.get('host', '').lower(), urlparse(public_base_url()).netloc.lower()}
        for h in os.getenv('ALLOWED_HOSTS', '').split(','):
            h = h.strip().lower()
            if h and h != '*': hosts.add(h)
        return {h for h in hosts if h}

    async def dispatch(self, request, call_next):
        if request.method in self.SAFE or request.headers.get('authorization', '').lower().startswith('bearer '):
            return await call_next(request)
        deny = JSONResponse({'detail': 'Requête refusée : origine non autorisée.'}, status_code=403)
        if request.headers.get('sec-fetch-site', '').lower() == 'cross-site': return deny
        source = request.headers.get('origin') or request.headers.get('referer')
        if source:
            if source == 'null': return deny
            host = urlparse(source).netloc.lower()
            allowed = self._allowed(request)
            if host not in allowed and host.split(':')[0] not in allowed: return deny
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault('X-Content-Type-Options', 'nosniff')
        h.setdefault('X-Frame-Options', 'DENY')
        h.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        h.setdefault('Permissions-Policy', 'camera=(self), microphone=(), geolocation=()')
        h.setdefault('Content-Security-Policy', CSP)
        h.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        if is_production(): h.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response
