"""
Endpoints systeme.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.api.dependencies import get_current_user
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/status")
async def status():
    from backend.database.connection import obtenir_connexion
    conn = obtenir_connexion()

    cursor = conn.execute("SELECT COUNT(*) FROM matches")
    total_matchs = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE status = 'upcoming'"
    )
    matchs_a_venir = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM match_features")
    total_features = cursor.fetchone()[0]

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "system_mode": "active",
                "api_status": "operational",
                "total_matchs": total_matchs,
                "matchs_a_venir": matchs_a_venir,
                "total_features": total_features,
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
