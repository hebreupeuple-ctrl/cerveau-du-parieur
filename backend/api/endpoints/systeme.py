"""
Endpoints systeme.
"""

import time
import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.api.dependencies import get_db, get_current_user
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
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Déclenche une synchronisation légère à la demande :
    - resynchronisation des ligues actives du package
    - rafraîchissement des matchs du jour
    - collecte des cotes des prochaines 48h
    - régénération des pronostics pending de l'utilisateur
    """
    from backend.analysis.accumulateur import GenerateurPronostics
    from backend.data.collector import DataCollector
    from backend.data.sync import synchroniser_ligues
    from backend.odds.collector import OddsCollector

    logger.info_ctx(
        "Synchronisation manuelle demandee",
        context={"user_id": current_user["id"]},
    )

    sync_ligues = await synchroniser_ligues(conn)

    data_collector = DataCollector(conn)
    try:
        matchs_du_jour = await data_collector.collecter_matchs_aujourdhui()
    finally:
        await data_collector.fermer()

    odds_collector = OddsCollector(conn)
    try:
        cotes = await odds_collector.collecter_cotes_matchs_a_venir(heures=48)
    finally:
        await odds_collector.fermer()

    generateur = GenerateurPronostics(conn)
    pronostics = generateur.generer_pronostics_du_jour(
        user_id=current_user["id"],
        bankroll=current_user["current_bankroll"],
        bankroll_initiale=current_user["initial_bankroll"],
        fraction_override=current_user["kelly_fraction"],
        max_pronostics=10,
    )

    conn.execute(
        """
        DELETE FROM pronostics
        WHERE user_id = ?
        AND status = 'pending'
        """,
        (current_user["id"],),
    )

    inserted = 0
    for pronostic in pronostics:
        conn.execute(
            """
            INSERT INTO pronostics (
                user_id, match_id, market,
                model_probability, bookmaker_probability, probability_edge,
                expected_value, reference_bookmaker, reference_odds,
                confidence_score, kelly_fraction_used, kelly_raw,
                recommended_stake, bankroll_at_recommendation, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                current_user["id"],
                pronostic["match_id"],
                pronostic["marche"],
                pronostic["probabilite_modele"],
                pronostic["probabilite_bookmaker"],
                pronostic["edge"],
                pronostic["ev"],
                "footystats",
                pronostic["cote"],
                pronostic["confiance"],
                pronostic["kelly_fraction"],
                pronostic["kelly_brut"],
                pronostic["mise_recommandee"],
                current_user["current_bankroll"],
            ),
        )
        inserted += 1

    conn.commit()

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
                "matchs_du_jour": matchs_du_jour,
                "cotes": cotes,
                "pronostics_generated": len(pronostics),
                "pronostics_inserted": inserted,
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
