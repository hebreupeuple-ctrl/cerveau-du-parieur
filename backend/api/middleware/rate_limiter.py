"""
Rate limiter en mémoire par IP.
Utilise un algorithme de fenêtre glissante (sliding window).

Limites :
- 60 requêtes / minute par IP pour les endpoints généraux
- 10 requêtes / minute par IP pour les endpoints d'authentification (/auth/login, /auth/register)

Le stockage est en mémoire : se réinitialise au redémarrage du serveur.
Pour un déploiement multi-instances, remplacer par Redis.
"""

import time
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.core.config import settings

# Nettoyer les IPs inactives toutes les N requêtes
_CLEANUP_INTERVAL = 10_000

# Chemins soumis à une limite stricte (anti-brute-force)
AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}
AUTH_LIMIT  = 10   # requêtes
AUTH_WINDOW = 60   # secondes

# Limite générale pour tous les autres endpoints
GENERAL_LIMIT  = 120  # requêtes
GENERAL_WINDOW = 60   # secondes


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limiting basé sur les fenêtres glissantes par IP.
    """

    def __init__(self, app):
        super().__init__(app)
        # {ip: deque de timestamps}
        self._auth_buckets:    dict[str, deque] = defaultdict(deque)
        self._general_buckets: dict[str, deque] = defaultdict(deque)
        self._request_count: int = 0

    def _get_client_ip(self, request: Request) -> str:
        """Extrait l'IP réelle (gère les proxies Railway/Heroku)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _est_autorise(self, bucket: deque, limit: int, window: int) -> bool:
        """
        Vérifie si la requête est dans la limite.
        Nettoie les timestamps expirés de la fenêtre.
        """
        now = time.time()
        # Purger les entrées hors fenêtre
        while bucket and bucket[0] < now - window:
            bucket.popleft()

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True

    def _purger_ips_inactives(self, now: float) -> None:
        """Supprime les IPs dont le bucket est vide ou entièrement expiré."""
        for buckets, window in (
            (self._auth_buckets, AUTH_WINDOW),
            (self._general_buckets, GENERAL_WINDOW),
        ):
            cutoff = now - window
            stale = [ip for ip, dq in buckets.items() if not dq or dq[-1] < cutoff]
            for ip in stale:
                del buckets[ip]

    async def dispatch(self, request: Request, call_next):
        # Désactivé en mode test pour ne pas perturber les suites de tests
        if settings.ENVIRONMENT == "test":
            return await call_next(request)

        self._request_count += 1
        if self._request_count % _CLEANUP_INTERVAL == 0:
            self._purger_ips_inactives(time.time())

        path = request.url.path

        # Ignorer les endpoints non-API (health, docs, assets)
        if not path.startswith("/api/"):
            return await call_next(request)

        ip = self._get_client_ip(request)

        if path in AUTH_PATHS:
            if not self._est_autorise(self._auth_buckets[ip], AUTH_LIMIT, AUTH_WINDOW):
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Trop de tentatives. Réessayez dans {AUTH_WINDOW}s.",
                        },
                    },
                    headers={"Retry-After": str(AUTH_WINDOW)},
                )
        else:
            if not self._est_autorise(self._general_buckets[ip], GENERAL_LIMIT, GENERAL_WINDOW):
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Trop de requêtes. Réessayez dans {GENERAL_WINDOW}s.",
                        },
                    },
                    headers={"Retry-After": str(GENERAL_WINDOW)},
                )

        return await call_next(request)
