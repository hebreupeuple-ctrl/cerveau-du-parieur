"""
Endpoints pronostics.
"""

import time
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3

from backend.api.dependencies import get_db, get_current_user
from backend.analysis.accumulateur import GenerateurPronostics

router = APIRouter()


def reponse_succes(data: dict):
    return JSONResponse(content={
        "success": True,
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
    })


@router.get("/today")
async def pronostics_du_jour(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    maintenant = int(time.time())
    dans_48h = maintenant + (48 * 3600)

    pronostics_db = conn.execute(
        """
        SELECT p.*,
               m.match_timestamp, m.home_team_id, m.away_team_id,
               t1.name as home_team, t2.name as away_team,
               l.name as league_name
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        JOIN leagues l ON m.league_id = l.id
        WHERE p.user_id = ?
        AND p.status = 'pending'
        AND m.match_timestamp BETWEEN ? AND ?
        ORDER BY p.confidence_score DESC
        """,
        (current_user["id"], maintenant, dans_48h),
    ).fetchall()

    pronostics_formatted = []
    for p in pronostics_db:
        pronostics_formatted.append({
            "id": p["id"],
            "match": {
                "id": p["match_id"],
                "home_team": p["home_team"],
                "away_team": p["away_team"],
                "league": p["league_name"],
                "kickoff_timestamp": p["match_timestamp"],
            },
            "market": p["market"],
            "market_label": p["market"],
            "reference_bookmaker": p["reference_bookmaker"],
            "reference_odds": p["reference_odds"],
            "model_probability": p["model_probability"],
            "bookmaker_probability": p["bookmaker_probability"],
            "probability_edge": p["probability_edge"],
            "expected_value": p["expected_value"],
            "confidence_score": p["confidence_score"],
            "recommended_stake": p["recommended_stake"],
            "potential_gain": round(p["recommended_stake"] * p["reference_odds"], 2),
            "status": p["status"],
        })

    return reponse_succes({
        "system_mode": current_user["system_mode"],
        "pronostics": pronostics_formatted,
        "combine_recommendation": None,
        "bankroll_summary": {
            "current": current_user["current_bankroll"],
            "today_change": 0,
            "week_change": 0,
            "week_change_pct": 0,
        }
    })


class PlaceRequest(BaseModel):
    actual_stake: float
    actual_odds: float


@router.post("/{pronostic_id}/place")
async def placer_pari(
    pronostic_id: int,
    req: PlaceRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    pronostic = conn.execute(
        "SELECT * FROM pronostics WHERE id = ? AND user_id = ?",
        (pronostic_id, current_user["id"]),
    ).fetchone()

    if not pronostic:
        raise HTTPException(status_code=404, detail="Pronostic introuvable")

    if pronostic["status"] != "pending":
        raise HTTPException(status_code=409, detail="Pari déjà placé ou ignoré")

    match = conn.execute(
        "SELECT match_timestamp FROM matches WHERE id = ?",
        (pronostic["match_id"],),
    ).fetchone()

    if match and match["match_timestamp"] < int(time.time()):
        raise HTTPException(status_code=409, detail="Le match a déjà commencé")

    conn.execute(
        """
        UPDATE pronostics SET
            status = 'placed',
            actual_stake = ?,
            actual_odds = ?,
            placed_at = datetime('now')
        WHERE id = ?
        """,
        (req.actual_stake, req.actual_odds, pronostic_id),
    )

    nouvelle_bankroll = current_user["current_bankroll"] - req.actual_stake
    conn.execute(
        "UPDATE users SET current_bankroll = ? WHERE id = ?",
        (nouvelle_bankroll, current_user["id"]),
    )
    conn.commit()

    return reponse_succes({
        "pronostic_id": pronostic_id,
        "status": "placed",
        "actual_stake": req.actual_stake,
        "actual_odds": req.actual_odds,
        "new_bankroll": nouvelle_bankroll,
    })


class IgnoreRequest(BaseModel):
    reason: str = None


@router.post("/{pronostic_id}/ignore")
async def ignorer_pronostic(
    pronostic_id: int,
    req: IgnoreRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    conn.execute(
        """
        UPDATE pronostics SET
            status = 'ignored',
            ignored_at = datetime('now'),
            ignore_reason = ?
        WHERE id = ? AND user_id = ?
        """,
        (req.reason, pronostic_id, current_user["id"]),
    )
    conn.commit()

    return reponse_succes({"pronostic_id": pronostic_id, "status": "ignored"})
