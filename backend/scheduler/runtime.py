"""
Scheduler applicatif leger base sur asyncio.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.connection import creer_connexion
from backend.scheduler.locks import DistributedJobLockService
from backend.scheduler.tasks.automation import (
    auto_resoudre_pronostics_termines,
    backfill_features_historiques,
    entrainer_modele,
    rafraichir_matchs_cotes_et_pronostics,
    recalibrer_modele,
    sauvegarder_base_de_donnees,
    synchroniser_catalogue_et_automatiser_si_necessaire,
)

logger = get_logger(__name__)
SYSTEM_PIPELINE_RESOURCE = "system_pipeline"


class AutomationScheduler:
    def __init__(self):
        self._tasks: list[asyncio.Task] = []
        self._locks: dict[str, asyncio.Lock] = {}
        self._started = False
        self._distributed_locks = DistributedJobLockService()

    async def start(self) -> None:
        if self._started or not settings.SCHEDULER_ENABLED:
            return

        self._started = True

        logger.info("Demarrage du scheduler applicatif")

        if settings.AUTO_SYNC_ON_STARTUP:
            self._tasks.append(
                asyncio.create_task(self._bootstrap())
            )

        self._tasks.extend([
                asyncio.create_task(
                    self._boucle_job(
                        "sync_leagues",
                        synchroniser_catalogue_et_automatiser_si_necessaire,
                        settings.LEAGUE_SYNC_INTERVAL_HOURS * 3600,
                        resource_name=SYSTEM_PIPELINE_RESOURCE,
                    )
                ),
                asyncio.create_task(
                    self._boucle_job(
                        "market_refresh",
                        rafraichir_matchs_cotes_et_pronostics,
                        settings.MARKET_REFRESH_INTERVAL_MINUTES * 60,
                        resource_name=SYSTEM_PIPELINE_RESOURCE,
                    )
                ),
                # Résolution indépendante : pas d'appel API, juste SQL.
                # Tourne toutes les 5 min pour corriger les pronostics
                # dès que FootyStats met les scores à jour.
                asyncio.create_task(
                    self._boucle_job(
                        "resolution",
                        auto_resoudre_pronostics_termines,
                        settings.RESOLUTION_INTERVAL_MINUTES * 60,
                    )
                ),
            asyncio.create_task(
                self._boucle_job(
                    "model_retrain",
                    entrainer_modele,
                    settings.MODEL_RETRAIN_INTERVAL_HOURS * 3600,
                    initial_delay_seconds=(
                        settings.MODEL_RETRAIN_INITIAL_DELAY_MINUTES * 60
                    ),
                    resource_name=SYSTEM_PIPELINE_RESOURCE,
                )
            ),
            asyncio.create_task(
                self._boucle_job(
                    "platt_recalibration",
                    recalibrer_modele,
                    settings.PLATT_RECAL_INTERVAL_HOURS * 3600,
                    initial_delay_seconds=7200,  # 2h après démarrage
                    resource_name=SYSTEM_PIPELINE_RESOURCE,
                )
            ),
        ])

        if settings.HISTORICAL_FEATURE_BACKFILL_ENABLED:
            self._tasks.append(
                asyncio.create_task(
                    self._boucle_job(
                        "historical_feature_backfill",
                        backfill_features_historiques,
                        settings.HISTORICAL_FEATURE_BACKFILL_INTERVAL_MINUTES * 60,
                        resource_name=SYSTEM_PIPELINE_RESOURCE,
                    )
                )
            )

        self._tasks.append(
            asyncio.create_task(
                self._boucle_job(
                    "daily_backup",
                    sauvegarder_base_de_donnees,
                    24 * 3600,
                    initial_delay_seconds=3600,
                )
            )
        )

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()

        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks = []
        self._started = False
        logger.info("Arret du scheduler applicatif")

    async def _bootstrap(self) -> None:
        sync_result = await self._executer_job(
            "sync_leagues",
            synchroniser_catalogue_et_automatiser_si_necessaire,
            resource_name=SYSTEM_PIPELINE_RESOURCE,
        )
        if not (sync_result or {}).get("pipeline_triggered"):
            await self._executer_job(
                "market_refresh",
                rafraichir_matchs_cotes_et_pronostics,
                resource_name=SYSTEM_PIPELINE_RESOURCE,
            )
        if (
            settings.HISTORICAL_FEATURE_BACKFILL_ENABLED
            and not (sync_result or {}).get("pipeline_triggered")
        ):
            await self._executer_job(
                "historical_feature_backfill",
                backfill_features_historiques,
                resource_name=SYSTEM_PIPELINE_RESOURCE,
            )

    async def _boucle_job(
        self,
        job_name: str,
        job_fn: Callable[[], Awaitable[dict]],
        interval_seconds: int,
        initial_delay_seconds: int = 0,
        resource_name: str = None,
        max_retries: int = 3,
    ) -> None:
        """
        Boucle principale d'un job périodique.
        En cas d'échec, relance avec backoff exponentiel (2^n × 30s, max 10 min)
        avant de rendre la main à l'intervalle normal.
        """
        try:
            if initial_delay_seconds > 0:
                await asyncio.sleep(initial_delay_seconds)
            else:
                await asyncio.sleep(interval_seconds)

            while True:
                succes = False
                for tentative in range(1, max_retries + 1):
                    try:
                        await self._executer_job(
                            job_name,
                            job_fn,
                            resource_name=resource_name,
                        )
                        succes = True
                        break
                    except Exception as exc:
                        if tentative < max_retries:
                            delai_retry = min(30 * (2 ** (tentative - 1)), 600)
                            logger.warning_ctx(
                                "Job échoué — retry dans %ds (tentative %d/%d)",
                                context={
                                    "job_name": job_name,
                                    "tentative": tentative,
                                    "max_retries": max_retries,
                                    "delai_retry_s": delai_retry,
                                    "erreur": str(exc),
                                },
                            )
                            await asyncio.sleep(delai_retry)
                        else:
                            logger.error_ctx(
                                "Job abandonné après %d tentatives",
                                context={
                                    "job_name": job_name,
                                    "tentatives": max_retries,
                                    "erreur": str(exc),
                                },
                            )

                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _executer_job(
        self,
        job_name: str,
        job_fn: Callable[[], Awaitable[dict]],
        resource_name: str = None,
    ) -> dict | None:
        resource_name = resource_name or job_name
        if resource_name not in self._locks:
            # Evite la croissance illimitée du dict en nettoyant les locks inutilisés
            if len(self._locks) > 50:
                stale = [k for k, v in self._locks.items() if not v.locked()]
                for k in stale:
                    del self._locks[k]
            self._locks[resource_name] = asyncio.Lock()
        lock = self._locks[resource_name]
        if lock.locked():
            logger.warning_ctx(
                "Job ignore car deja en cours",
                context={
                    "job_name": job_name,
                    "resource_name": resource_name,
                },
            )
            return None

        async with lock:
            lock_token = await asyncio.to_thread(
                self._distributed_locks.acquire,
                resource_name,
            )
            if not lock_token:
                logger.warning_ctx(
                    "Job ignore car verrou distribue indisponible",
                    context={
                        "job_name": job_name,
                        "resource_name": resource_name,
                    },
                )
                return None

            job_id = self._creer_job_log(job_name)
            debut = time.time()

            try:
                resultat = await job_fn()
                self._terminer_job_log(
                    job_id=job_id,
                    status="completed",
                    execution_time_ms=int((time.time() - debut) * 1000),
                    result_summary_json=json.dumps(
                        resultat,
                        ensure_ascii=False,
                        default=str,
                    ),
                )
                logger.info_ctx(
                    "Job automatise termine",
                    context={"job_name": job_name},
                )
                return resultat
            except Exception as exc:
                self._terminer_job_log(
                    job_id=job_id,
                    status="failed",
                    execution_time_ms=int((time.time() - debut) * 1000),
                    error_message=str(exc),
                )
                logger.error_ctx(
                    "Job automatise en echec",
                    context={
                        "job_name": job_name,
                        "erreur": str(exc),
                    },
                )
                return None
            finally:
                await asyncio.to_thread(
                    self._distributed_locks.release,
                    resource_name,
                    lock_token,
                )

    def _creer_job_log(self, job_name: str) -> int:
        conn = creer_connexion()
        try:
            cursor = conn.execute(
                """
                INSERT INTO scheduler_jobs (
                    job_name, started_at, status,
                    attempt_number, max_attempts
                ) VALUES (?, ?, 'running', 1, 1)
                """,
                (
                    job_name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _terminer_job_log(
        self,
        job_id: int,
        status: str,
        execution_time_ms: int,
        result_summary_json: str = None,
        error_message: str = None,
    ) -> None:
        conn = creer_connexion()
        try:
            conn.execute(
                """
                UPDATE scheduler_jobs SET
                    completed_at = ?,
                    status = ?,
                    execution_time_ms = ?,
                    result_summary_json = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    execution_time_ms,
                    result_summary_json,
                    error_message,
                    job_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
