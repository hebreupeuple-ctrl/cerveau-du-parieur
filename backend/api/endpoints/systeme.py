"""
Endpoints systeme.
"""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.api.dependencies import get_current_admin_user
from backend.core.logging import get_logger
from backend.scheduler.locks import DistributedJobLockService

router = APIRouter()
logger = get_logger(__name__)
manual_system_lock = asyncio.Lock()
SYSTEM_PIPELINE_RESOURCE = "system_pipeline"


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/status")
async def status():
    from backend.database.connection import obtenir_connexion
    from backend.scheduler.tasks.automation import (
        obtenir_resume_features_historiques,
    )

    conn = obtenir_connexion()

    cursor = conn.execute("SELECT COUNT(*) FROM matches")
    total_matchs = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE status = 'upcoming'"
    )
    matchs_a_venir = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM match_features")
    total_features = cursor.fetchone()[0]
    historical_features = obtenir_resume_features_historiques(conn)

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "system_mode": "active",
                "api_status": "operational",
                "total_matchs": total_matchs,
                "matchs_a_venir": matchs_a_venir,
                "total_features": total_features,
                **historical_features,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
    )


@router.post("/manual-sync")
async def manual_sync(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Déclenche une synchronisation légère à la demande :
    - resynchronisation des ligues actives du package
    - rafraîchissement des matchs du jour
    - collecte des cotes des prochaines 48h
    - régénération des pronostics pending de l'utilisateur
    """
    from backend.scheduler.tasks.automation import (
        rafraichir_matchs_cotes_et_pronostics,
        synchroniser_catalogue,
    )

    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    logger.info_ctx(
        "Synchronisation manuelle demandee",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            sync_ligues = await synchroniser_catalogue()
            refresh = await rafraichir_matchs_cotes_et_pronostics(
                heures=48,
                user_ids=[current_user["id"]],
                max_pronostics=10,
            )
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )
    inserted = refresh["pronostics"]["inserted"]

    logger.info_ctx(
        "Synchronisation manuelle terminee",
        context={
            "user_id": current_user["id"],
            "pronostics_inserted": inserted,
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "sync_ligues": sync_ligues,
                "matchs_du_jour": refresh["matchs_du_jour"],
                "cotes": refresh["cotes"],
                "features": refresh["features"],
                "pronostics_generated": refresh["pronostics"]["inserted"],
                "pronostics_inserted": inserted,
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )


@router.post("/manual-feature-backfill")
async def manual_feature_backfill(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Déclenche un lot manuel de backfill des features historiques.
    """
    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    from backend.scheduler.tasks.automation import (
        backfill_features_historiques,
    )

    logger.info_ctx(
        "Backfill historique manuel demande",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultat = await backfill_features_historiques()
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    logger.info_ctx(
        "Backfill historique manuel termine",
        context={
            "user_id": current_user["id"],
            "processed": resultat.get("processed", 0),
            "remaining": resultat.get("after", {}).get(
                "features_historiques_manquantes",
            ),
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": resultat,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )


@router.post("/manual-retrain")
async def manual_retrain(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Déclenche un réentraînement manuel du modèle actif.
    """
    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    from backend.database.connection import obtenir_connexion
    from backend.scheduler.tasks.automation import entrainer_modele

    logger.info_ctx(
        "Entrainement manuel demande",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultats = await entrainer_modele()
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    conn = obtenir_connexion()
    version = conn.execute(
        """
        SELECT version, trained_at, brier_score_over25, auc_roc_over25
        FROM model_versions
        WHERE is_active = 1
        LIMIT 1
        """
    ).fetchone()

    logger.info_ctx(
        "Entrainement manuel termine",
        context={
            "user_id": current_user["id"],
            "markets": resultats.get("markets", []),
            "version": version["version"] if version else None,
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "trained": bool(resultats.get("markets")),
                "markets": resultats.get("markets", []),
                "metrics": resultats.get("metrics", {}),
                "model_health": {
                    "model_version": version["version"] if version else None,
                    "last_retrain": version["trained_at"] if version else None,
                    "brier_score": (
                        version["brier_score_over25"] if version else None
                    ),
                    "auc_roc": (
                        version["auc_roc_over25"] if version else None
                    ),
                },
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
