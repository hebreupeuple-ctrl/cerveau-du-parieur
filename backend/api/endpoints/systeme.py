"""
Endpoints systeme.
"""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.api.dependencies import get_current_user
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)
manual_backfill_lock = asyncio.Lock()
manual_retrain_lock = asyncio.Lock()


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
    current_user: dict = Depends(get_current_user),
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

    logger.info_ctx(
        "Synchronisation manuelle demandee",
        context={"user_id": current_user["id"]},
    )

    sync_ligues = await synchroniser_catalogue()
    refresh = await rafraichir_matchs_cotes_et_pronostics(
        heures=48,
        user_ids=[current_user["id"]],
        max_pronostics=10,
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
    current_user: dict = Depends(get_current_user),
):
    """
    Déclenche un lot manuel de backfill des features historiques.
    """
    if manual_retrain_lock.locked():
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "RETRAIN_IN_PROGRESS",
                    "message": "Attends la fin de l'entraînement avant le backfill",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if manual_backfill_lock.locked():
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "BACKFILL_IN_PROGRESS",
                    "message": "Un backfill historique est déjà en cours",
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

    async with manual_backfill_lock:
        resultat = await backfill_features_historiques()

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
    current_user: dict = Depends(get_current_user),
):
    """
    Déclenche un réentraînement manuel du modèle actif.
    """
    if manual_backfill_lock.locked():
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "BACKFILL_IN_PROGRESS",
                    "message": "Attends la fin du backfill historique avant l'entraînement",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    if manual_retrain_lock.locked():
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "RETRAIN_IN_PROGRESS",
                    "message": "Un entraînement est déjà en cours",
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

    async with manual_retrain_lock:
        resultats = await entrainer_modele()

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
