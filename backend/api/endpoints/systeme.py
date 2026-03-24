"""
Endpoints systeme.
"""

import time
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


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
