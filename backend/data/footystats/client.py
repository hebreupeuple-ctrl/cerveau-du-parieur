"""
Client HTTP pour l'API FootyStats.
Gère les appels API avec rate limiting et retry.
"""

import time
import asyncio
from typing import Any, Optional
import httpx
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.exceptions import (
    FootyStatsUnavailableException,
    RateLimitExceededException,
)

logger = get_logger(__name__)


class FootyStatsRateLimiter:
    """
    Rate limiter singleton partagé entre toutes les tâches.
    Garantit de ne jamais dépasser 1600 requêtes par heure.
    """

    _instance: Optional["FootyStatsRateLimiter"] = None
    _compteur: int = 0
    _reset_at: float = 0.0
    _lock: asyncio.Lock = None

    def __new__(cls) -> "FootyStatsRateLimiter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = asyncio.Lock()
            cls._instance._reset_at = time.time() + 3600
        return cls._instance

    async def peut_faire_requete(self) -> bool:
        """
        Vérifie si une requête peut être faite.
        Réinitialise le compteur si l'heure est passée.
        """
        async with self._lock:
            maintenant = time.time()
            if maintenant >= self._reset_at:
                self._compteur = 0
                self._reset_at = maintenant + 3600
                logger.info_ctx(
                    "Rate limiter réinitialisé",
                    context={"reset_at": self._reset_at},
                )

            if self._compteur >= settings.MAX_REQUESTS_PER_HOUR:
                logger.warning_ctx(
                    "Limite de requêtes atteinte",
                    context={
                        "compteur": self._compteur,
                        "reset_dans": int(self._reset_at - maintenant),
                    },
                )
                return False

            self._compteur += 1
            return True

    async def attendre_si_necessaire(self) -> None:
        """
        Attend que le rate limit soit réinitialisé
        si la limite est atteinte.
        """
        while not await self.peut_faire_requete():
            maintenant = time.time()
            attente = max(1, self._reset_at - maintenant)
            logger.info_ctx(
                "Attente rate limit",
                context={"attente_secondes": int(attente)},
            )
            await asyncio.sleep(min(attente, 60))

    @property
    def compteur(self) -> int:
        return self._compteur


class FootyStatsClient:
    """
    Client HTTP pour l'API FootyStats.
    Gère l'authentification, le rate limiting et les erreurs.
    """

    BASE_URL = "https://api.football-data-api.com"

    def __init__(self):
        self.api_key = settings.FOOTYSTATS_API_KEY
        self.rate_limiter = FootyStatsRateLimiter()
        self._client: Optional[httpx.AsyncClient] = None

    async def _obtenir_client(self) -> httpx.AsyncClient:
        """
        Retourne le client HTTP.
        Crée le client s'il n'existe pas.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "CerveauDuParieur/1.0"},
            )
        return self._client

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] = None,
        max_retries: int = 3,
    ) -> dict:
        """
        Effectue un appel GET à l'API FootyStats.
        Gère le rate limiting et les retries automatiquement.
        """
        await self.rate_limiter.attendre_si_necessaire()

        if params is None:
            params = {}
        params["key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"
        derniere_erreur = None

        for tentative in range(1, max_retries + 1):
            try:
                debut = time.time()
                client = await self._obtenir_client()
                response = await client.get(
                    url, params=params
                )
                duree_ms = int((time.time() - debut) * 1000)

                if duree_ms > 5000:
                    logger.warning_ctx(
                        "FootyStats API lente",
                        context={
                            "endpoint": endpoint,
                            "duree_ms": duree_ms,
                        },
                    )

                response.raise_for_status()
                data = response.json()

                logger.info_ctx(
                    "Appel FootyStats réussi",
                    context={
                        "endpoint": endpoint,
                        "duree_ms": duree_ms,
                        "requetes_utilisees": self.rate_limiter.compteur,
                    },
                )

                return data

            except httpx.TimeoutException as e:
                derniere_erreur = e
                logger.warning_ctx(
                    f"Timeout FootyStats (tentative {tentative}/{max_retries})",
                    context={"endpoint": endpoint},
                )

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning_ctx(
                        "Rate limit FootyStats atteint",
                        context={"endpoint": endpoint},
                    )
                    await asyncio.sleep(60)
                    continue
                derniere_erreur = e
                logger.error_ctx(
                    f"Erreur HTTP FootyStats {e.response.status_code}",
                    context={
                        "endpoint": endpoint,
                        "status": e.response.status_code,
                    },
                )

            except Exception as e:
                derniere_erreur = e
                logger.error_ctx(
                    f"Erreur FootyStats (tentative {tentative})",
                    context={
                        "endpoint": endpoint,
                        "erreur": str(e),
                    },
                )

            if tentative < max_retries:
                await asyncio.sleep(2 ** tentative)

        logger.critical_ctx(
            "FootyStats API définitivement inaccessible",
            context={
                "endpoint": endpoint,
                "tentatives": max_retries,
                "erreur": str(derniere_erreur),
            },
        )
        raise FootyStatsUnavailableException()

    async def verifier_connexion(self) -> bool:
        """
        Vérifie que la clé API est valide.
        """
        try:
            response = await self.get(
                "league-list",
                params={"chosen_leagues_only": "true"},
                max_retries=1,
            )
            return bool(response)
        except Exception:
            return False

    async def fermer(self) -> None:
        """
        Ferme proprement le client HTTP.
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()
