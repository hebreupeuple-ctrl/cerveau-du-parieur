"""
Endpoints pronostics.
"""

import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import sqlite3

from backend.api.dependencies import get_db, get_current_user
from backend.core.config import settings
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def reponse_succes(data: dict):
    return JSONResponse(content={
        "success": True,
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
    })


def _charger_pronostics_pending(
    conn: sqlite3.Connection,
    user_id: int,
    maintenant: int,
    dans_48h: int,
):
    return conn.execute(
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
        (user_id, maintenant, dans_48h),
    ).fetchall()


@router.get("/today")
async def pronostics_du_jour(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    maintenant = int(time.time())
    dans_48h = maintenant + (48 * 3600)

    pronostics_db = _charger_pronostics_pending(
        conn,
        current_user["id"],
        maintenant,
        dans_48h,
    )

    if not pronostics_db:
        existing_window_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM pronostics p
            JOIN matches m ON p.match_id = m.id
            WHERE p.user_id = ?
            AND m.match_timestamp BETWEEN ? AND ?
            """,
            (current_user["id"], maintenant, dans_48h),
        ).fetchone()[0]

        if existing_window_count == 0:
            from backend.scheduler.tasks.automation import (
                generer_et_sauvegarder_pronostics_utilisateur,
            )

            user_row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (current_user["id"],),
            ).fetchone()

            if user_row:
                resultat = generer_et_sauvegarder_pronostics_utilisateur(
                    conn=conn,
                    user=user_row,
                    max_pronostics=10,
                    replace_pending=True,
                    commit=True,
                )
                if resultat["inserted"] > 0:
                    logger.info_ctx(
                        "Pronostics auto-generes a la premiere ouverture",
                        context={
                            "user_id": current_user["id"],
                            "inserted": resultat["inserted"],
                        },
                    )
                    pronostics_db = _charger_pronostics_pending(
                        conn,
                        current_user["id"],
                        maintenant,
                        dans_48h,
                    )

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
    actual_stake: float = Field(gt=0)
    actual_odds: float = Field(gt=1.0)


@router.post("/{pronostic_id}/place")
async def placer_pari(
    pronostic_id: int,
    req: PlaceRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        conn.execute("BEGIN IMMEDIATE")

        pronostic = conn.execute(
            "SELECT * FROM pronostics WHERE id = ? AND user_id = ?",
            (pronostic_id, current_user["id"]),
        ).fetchone()

        if not pronostic:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Pronostic introuvable")

        if pronostic["status"] != "pending":
            conn.rollback()
            raise HTTPException(status_code=409, detail="Pari déjà placé ou ignoré")

        match = conn.execute(
            "SELECT match_timestamp FROM matches WHERE id = ?",
            (pronostic["match_id"],),
        ).fetchone()

        if match and match["match_timestamp"] < int(time.time()):
            conn.rollback()
            raise HTTPException(status_code=409, detail="Le match a déjà commencé")

        user_row = conn.execute(
            "SELECT current_bankroll FROM users WHERE id = ?",
            (current_user["id"],),
        ).fetchone()
        bankroll_avant = user_row["current_bankroll"] if user_row else 0

        if req.actual_stake < settings.MIN_STAKE:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Mise minimale: {settings.MIN_STAKE}",
            )

        if req.actual_stake > bankroll_avant:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="Bankroll insuffisante",
            )

        nouvelle_bankroll = round(bankroll_avant - req.actual_stake, 2)

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

        conn.execute(
            """
            UPDATE users SET
                current_bankroll = ?,
                bankroll_updated_at = datetime('now')
            WHERE id = ?
            """,
            (nouvelle_bankroll, current_user["id"]),
        )

        conn.execute(
            """
            INSERT INTO bankroll_transactions (
                user_id, pronostic_id, transaction_type,
                amount, balance_before, balance_after, reference_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_user["id"],
                pronostic_id,
                "bet_placed",
                -req.actual_stake,
                bankroll_avant,
                nouvelle_bankroll,
                f"Pari place sur {pronostic['market']}",
            ),
        )

        conn.commit()
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise

    return reponse_succes({
        "pronostic_id": pronostic_id,
        "status": "placed",
        "actual_stake": req.actual_stake,
        "actual_odds": req.actual_odds,
        "new_bankroll": nouvelle_bankroll,
    })


class ResolveRequest(BaseModel):
    result: str = Field(..., pattern="^(won|lost|void)$")


@router.post("/{pronostic_id}/resolve")
async def resoudre_pronostic(
    pronostic_id: int,
    req: ResolveRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Résout un pronostic placé : enregistre le résultat (won/lost/void),
    calcule le profit réel et met à jour la bankroll.
    """
    try:
        conn.execute("BEGIN IMMEDIATE")

        pronostic = conn.execute(
            "SELECT * FROM pronostics WHERE id = ? AND user_id = ?",
            (pronostic_id, current_user["id"]),
        ).fetchone()

        if not pronostic:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Pronostic introuvable")

        if pronostic["status"] != "placed":
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="Seuls les paris placés peuvent être résolus",
            )

        stake = pronostic["actual_stake"] or 0.0
        odds = pronostic["actual_odds"] or 1.0

        if req.result == "won":
            profit = round(stake * (odds - 1.0), 2)
            retour = round(stake + profit, 2)
        elif req.result == "lost":
            profit = -stake
            retour = 0.0
        else:  # void
            profit = 0.0
            retour = stake

        user_row = conn.execute(
            "SELECT current_bankroll FROM users WHERE id = ?",
            (current_user["id"],),
        ).fetchone()
        bankroll_avant = user_row["current_bankroll"] if user_row else 0.0
        nouvelle_bankroll = round(bankroll_avant + retour, 2)

        conn.execute(
            """
            UPDATE pronostics SET
                status = ?,
                actual_profit = ?,
                resolved_at = datetime('now')
            WHERE id = ?
            """,
            (req.result, profit, pronostic_id),
        )

        conn.execute(
            """
            UPDATE users SET
                current_bankroll = ?,
                bankroll_updated_at = datetime('now')
            WHERE id = ?
            """,
            (nouvelle_bankroll, current_user["id"]),
        )

        transaction_type = (
            "bet_won" if req.result == "won"
            else "bet_void" if req.result == "void"
            else "bet_lost"
        )
        conn.execute(
            """
            INSERT INTO bankroll_transactions (
                user_id, pronostic_id, transaction_type,
                amount, balance_before, balance_after, reference_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_user["id"],
                pronostic_id,
                transaction_type,
                retour,
                bankroll_avant,
                nouvelle_bankroll,
                f"Résolution {req.result} — {pronostic['market']}",
            ),
        )

        conn.commit()
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise

    return reponse_succes({
        "pronostic_id": pronostic_id,
        "result": req.result,
        "profit": profit,
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
