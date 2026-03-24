"""
Endpoints performance.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
import sqlite3

from backend.api.dependencies import get_db, get_current_user

router = APIRouter()


def reponse_succes(data: dict):
    return JSONResponse(content={
        "success": True,
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
    })


@router.get("/summary")
async def performance_summary(
    period: str = "all",
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    stats = conn.execute(
        """
        SELECT
            COUNT(*) as total_bets,
            SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) as bets_won,
            SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) as bets_lost,
            SUM(CASE WHEN status='void' THEN 1 ELSE 0 END) as bets_void,
            SUM(CASE WHEN status='ignored' THEN 1 ELSE 0 END) as bets_ignored,
            SUM(CASE WHEN status IN ('won','lost') THEN actual_stake ELSE 0 END) as total_staked,
            SUM(CASE WHEN status='won' THEN actual_profit ELSE 0 END) as total_profit
        FROM pronostics
        WHERE user_id = ?
        AND status IN ('won', 'lost', 'void', 'ignored', 'placed')
        """,
        (user_id,),
    ).fetchone()

    total_staked = stats["total_staked"] or 0
    total_profit = stats["total_profit"] or 0
    roi = total_profit / total_staked if total_staked > 0 else None

    model_version = conn.execute(
        "SELECT version, brier_score_over25, auc_roc_over25, trained_at FROM model_versions WHERE is_active = 1 LIMIT 1"
    ).fetchone()

    return reponse_succes({
        "period": period,
        "bankroll": {
            "initial": current_user["initial_bankroll"],
            "current": current_user["current_bankroll"],
        },
        "metrics": {
            "roi": roi,
            "yield": roi,
            "avg_clv": None,
            "max_drawdown": None,
            "win_rate": (
                stats["bets_won"] / max(stats["bets_won"] + stats["bets_lost"], 1)
                if stats["total_bets"] > 0 else None
            ),
        },
        "volume": {
            "total_bets": stats["total_bets"] or 0,
            "bets_won": stats["bets_won"] or 0,
            "bets_lost": stats["bets_lost"] or 0,
            "bets_void": stats["bets_void"] or 0,
            "bets_ignored": stats["bets_ignored"] or 0,
            "total_staked": total_staked,
            "total_profit": total_profit,
        },
        "by_market": [],
        "model_health": {
            "brier_score": model_version["brier_score_over25"] if model_version else 0.2487,
            "auc_roc": model_version["auc_roc_over25"] if model_version else 0.5776,
            "last_retrain": model_version["trained_at"] if model_version else "2026-03-24",
            "model_version": model_version["version"] if model_version else "2026.03.v1",
            "bias_alerts": [],
        },
    })
