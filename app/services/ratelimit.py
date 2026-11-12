"""Limiteur de débit partagé (Redis) ou en mémoire (développement, un seul processus)."""
import os
from collections import defaultdict, deque
from time import monotonic
from fastapi import Request
from app.config import is_production


class LimiterUnavailable(Exception):
    pass


class Limiter:
    def __init__(self):
        self.hits = defaultdict(deque)
        self.redis = None
        url = os.getenv("RATE_LIMIT_REDIS_URL")
        if url:
            try:
                import redis
                self.redis = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
            except ImportError:
                if is_production():
                    raise RuntimeError("Installez redis pour activer le rate limiting partagé.")

    def disabled(self) -> bool:
        return os.getenv("RATE_LIMIT_DISABLED", "").lower() == "true" and not is_production()

    def count(self, key: str, window: int) -> int:
        if self.disabled(): return 0
        if self.redis:
            try:
                return int(self.redis.get(f"rl:{key}") or 0)
            except Exception as exc:
                raise LimiterUnavailable() from exc
        q = self.hits[key]; now = monotonic()
        while q and now - q[0] > window: q.popleft()
        return len(q)

    def record(self, key: str, window: int) -> int:
        """Enregistre un événement et renvoie le total dans la fenêtre."""
        if self.disabled(): return 0
        if self.redis:
            try:
                k = f"rl:{key}"; n = self.redis.incr(k)
                if n == 1: self.redis.expire(k, window)
                return int(n)
            except Exception as exc:
                raise LimiterUnavailable() from exc
        now = monotonic()
        if len(self.hits) > 5000:
            for old in [k for k, v in self.hits.items() if not v or now - v[-1] > 3600]: self.hits.pop(old, None)
        q = self.hits[key]
        while q and now - q[0] > window: q.popleft()
        q.append(now)
        return len(q)

    def retry_after(self, key: str, window: int) -> int:
        if self.redis:
            try: return max(1, int(self.redis.ttl(f"rl:{key}") or window))
            except Exception: return window
        return window


limiter = Limiter()


def client_ip(request: Request) -> str:
    """IP réelle du client. Derrière N reverse proxies de confiance (TRUSTED_PROXY_COUNT=N), on lit
    X-Forwarded-For en partant de la droite ; sinon on n'accorde aucune confiance à l'en-tête (usurpable)."""
    n = int(os.getenv("TRUSTED_PROXY_COUNT", "0") or 0)
    if n > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= n:
            return parts[-n]
    return request.client.host if request.client else "unknown"


# Échecs de connexion : par couple (identifiant, IP) et, plus large, par identifiant seul.
LOGIN_FAIL_RULES = (("ip", 5, 900), ("user", 30, 3600))


def login_keys(username: str, ip: str) -> dict:
    u = (username or "").strip().lower()[:80]
    return {"ip": f"loginfail:{u}:{ip}", "user": f"loginfail:{u}"}


def login_blocked(username: str, ip: str) -> int | None:
    """Renvoie un délai (secondes) si la connexion est bloquée, sinon None. Les succès ne comptent pas."""
    try:
        keys = login_keys(username, ip)
        for name, limit, window in LOGIN_FAIL_RULES:
            if limiter.count(keys[name], window) >= limit:
                return limiter.retry_after(keys[name], window)
    except LimiterUnavailable:
        if is_production(): return 60
    return None


def login_failed(username: str, ip: str) -> None:
    try:
        keys = login_keys(username, ip)
        for name, _limit, window in LOGIN_FAIL_RULES:
            limiter.record(keys[name], window)
    except LimiterUnavailable:
        pass
