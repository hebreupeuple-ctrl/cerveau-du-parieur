"""
Endpoints performance.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
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
    period: str = Query("all", pattern="^(week|month|all)$"),
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    user_id = current_user["id"]

    if period == "week":
        date_filter = "AND placed_at >= datetime('now', '-7 days')"
    elif period == "month":
        date_filter = "AND placed_at >= datetime('now', '-30 days')"
    else:
        date_filter = ""

    stats = conn.execute(
        f"""
        SELECT
            COUNT(*) as total_bets,
            SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) as bets_won,
            SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) as bets_lost,
            SUM(CASE WHEN status='void' THEN 1 ELSE 0 END) as bets_void,
            SUM(CASE WHEN status='ignored' THEN 1 ELSE 0 END) as bets_ignored,
            SUM(CASE WHEN status IN ('won','lost') THEN actual_stake ELSE 0 END) as total_staked,
            SUM(CASE WHEN status IN ('won', 'lost') THEN actual_profit ELSE 0 END) as total_profit
        FROM pronostics
        WHERE user_id = ?
        AND status IN ('won', 'lost', 'void', 'ignored')
        {date_filter}
        """,
        (user_id,),
    ).fetchone()

    total_staked = stats["total_staked"] or 0
    total_profit = stats["total_profit"] or 0
    roi = round(total_profit / total_staked, 4) if total_staked > 0 else None

    # ROI par marché
    by_market_rows = conn.execute(
        f"""
        SELECT
            market,
            COUNT(*) as total,
            SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN status IN ('won','lost') THEN actual_stake ELSE 0 END) as staked,
            SUM(CASE WHEN status IN ('won','lost') THEN actual_profit ELSE 0 END) as profit,
            AVG(CASE WHEN clv IS NOT NULL THEN clv END) as avg_clv
        FROM pronostics
        WHERE user_id = ?
        AND status IN ('won', 'lost', 'void')
        {date_filter}
        GROUP BY market
        ORDER BY profit DESC
        """,
        (user_id,),
    ).fetchall()

    by_market = []
    for row in by_market_rows:
        staked_m = row["staked"] or 0
        profit_m = row["profit"] or 0
        by_market.append({
            "market": row["market"],
            "total": row["total"],
            "won": row["won"] or 0,
            "lost": row["lost"] or 0,
            "win_rate": round(row["won"] / max((row["won"] or 0) + (row["lost"] or 0), 1), 4),
            "staked": round(staked_m, 2),
            "profit": round(profit_m, 2),
            "roi": round(profit_m / staked_m, 4) if staked_m > 0 else None,
            "avg_clv": round(row["avg_clv"], 2) if row["avg_clv"] is not None else None,
        })

    # ROI par ligue
    by_league_rows = conn.execute(
        f"""
        SELECT
            l.name as league_name,
            COUNT(*) as total,
            SUM(CASE WHEN p.status='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN p.status='lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN p.status IN ('won','lost') THEN p.actual_stake ELSE 0 END) as staked,
            SUM(CASE WHEN p.status IN ('won','lost') THEN p.actual_profit ELSE 0 END) as profit
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        JOIN leagues l ON m.league_id = l.id
        WHERE p.user_id = ?
        AND p.status IN ('won', 'lost', 'void')
        {date_filter}
        GROUP BY l.name
        ORDER BY profit DESC
        """,
        (user_id,),
    ).fetchall()

    by_league = []
    for row in by_league_rows:
        staked_l = row["staked"] or 0
        profit_l = row["profit"] or 0
        by_league.append({
            "league": row["league_name"],
            "total": row["total"],
            "won": row["won"] or 0,
            "lost": row["lost"] or 0,
            "win_rate": round(row["won"] / max((row["won"] or 0) + (row["lost"] or 0), 1), 4),
            "staked": round(staked_l, 2),
            "profit": round(profit_l, 2),
            "roi": round(profit_l / staked_l, 4) if staked_l > 0 else None,
        })

    # CLV moyen global (paris placed avec closing_odds renseigné)
    clv_row = conn.execute(
        f"""
        SELECT AVG(clv) as avg_clv, COUNT(clv) as n_clv
        FROM pronostics
        WHERE user_id = ?
        AND clv IS NOT NULL
        AND status IN ('won', 'lost', 'void')
        {date_filter}
        """,
        (user_id,),
    ).fetchone()
    avg_clv = round(clv_row["avg_clv"], 2) if clv_row["avg_clv"] is not None else None

    # Max drawdown : parcours chronologique des paris résolus
    drawdown_rows = conn.execute(
        f"""
        SELECT actual_stake, actual_profit
        FROM pronostics
        WHERE user_id = ?
        AND status IN ('won', 'lost')
        AND actual_stake > 0
        {date_filter}
        ORDER BY placed_at ASC
        """,
        (user_id,),
    ).fetchall()

    max_drawdown = None
    if drawdown_rows:
        bankroll_init = current_user["initial_bankroll"] or 1000.0
        bk = bankroll_init
        peak = bankroll_init
        max_dd = 0.0
        for r in drawdown_rows:
            bk += r["actual_profit"] or 0.0
            if bk > peak:
                peak = bk
            dd = (peak - bk) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        max_drawdown = round(max_dd, 4)

    model_version = conn.execute(
        """
        SELECT version, brier_score_over25, auc_roc_over25,
               trained_at, total_matches_trained,
               training_data_start, training_data_end
        FROM model_versions
        WHERE is_active = 1
        LIMIT 1
        """
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
            "avg_clv": avg_clv,
            "clv_sample_size": clv_row["n_clv"] if clv_row else 0,
            "max_drawdown": max_drawdown,
            "win_rate": (
                round(stats["bets_won"] / max(stats["bets_won"] + stats["bets_lost"], 1), 4)
                if stats["total_bets"] > 0 else None
            ),
        },
        "volume": {
            "total_bets": stats["total_bets"] or 0,
            "bets_won": stats["bets_won"] or 0,
            "bets_lost": stats["bets_lost"] or 0,
            "bets_void": stats["bets_void"] or 0,
            "bets_ignored": stats["bets_ignored"] or 0,
            "total_staked": round(total_staked, 2),
            "total_profit": round(total_profit, 2),
        },
        "by_market": by_market,
        "by_league": by_league,
        "model_health": {
            "brier_score": model_version["brier_score_over25"] if model_version else None,
            "auc_roc": model_version["auc_roc_over25"] if model_version else None,
            "last_retrain": model_version["trained_at"] if model_version else None,
            "model_version": model_version["version"] if model_version else None,
            "total_matches_trained": (
                model_version["total_matches_trained"] if model_version else 0
            ),
            "training_data_start": (
                model_version["training_data_start"] if model_version else None
            ),
            "training_data_end": (
                model_version["training_data_end"] if model_version else None
            ),
            "bias_alerts": [],
        },
    })


@router.get("/backtest")
async def backtest_kelly(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Simulation de l'évolution de la bankroll sur les paris résolus.
    Calcule: courbe bankroll, max drawdown, Sharpe, EV moyen réalisé.
    """
    user_id = current_user["id"]
    bankroll_initiale = current_user["initial_bankroll"] or 1000.0

    rows = conn.execute(
        """
        SELECT
            p.placed_at,
            p.market,
            p.reference_odds,
            p.model_probability,
            p.probability_edge,
            p.expected_value,
            p.actual_stake,
            p.actual_profit,
            p.status
        FROM pronostics p
        WHERE p.user_id = ?
        AND p.status IN ('won', 'lost')
        AND p.actual_stake > 0
        ORDER BY p.placed_at ASC
        """,
        (user_id,),
    ).fetchall()

    if not rows:
        return reponse_succes({
            "bankroll_initiale": bankroll_initiale,
            "n_paris": 0,
            "courbe": [],
            "metriques": {},
        })

    import math as _math

    bankroll = bankroll_initiale
    peak = bankroll_initiale
    max_drawdown = 0.0
    courbe = []
    rendements = []
    total_mise = 0.0
    total_profit = 0.0
    ev_sum = 0.0
    ev_count = 0

    for row in rows:
        profit = row["actual_profit"] or 0.0
        mise = row["actual_stake"] or 0.0
        bankroll += profit
        total_mise += mise
        total_profit += profit

        if bankroll > peak:
            peak = bankroll
        drawdown = (peak - bankroll) / peak if peak > 0 else 0.0
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        if row["expected_value"] is not None:
            ev_sum += row["expected_value"]
            ev_count += 1

        rendements.append(profit / mise if mise > 0 else 0.0)
        courbe.append({
            "date": row["placed_at"],
            "bankroll": round(bankroll, 2),
            "profit_cumul": round(total_profit, 2),
            "market": row["market"],
            "mise": round(mise, 2),
            "profit": round(profit, 2),
            "won": row["status"] == "won",
        })

    roi_global = round(total_profit / total_mise, 4) if total_mise > 0 else None
    avg_ev = round(ev_sum / ev_count, 4) if ev_count > 0 else None

    if len(rendements) > 1:
        mean_r = sum(rendements) / len(rendements)
        variance = sum((r - mean_r) ** 2 for r in rendements) / len(rendements)
        volatilite = round(_math.sqrt(variance), 4) if variance > 0 else 0.0
        sharpe = round(mean_r / volatilite, 3) if volatilite > 0 else None
    else:
        volatilite = None
        sharpe = None

    return reponse_succes({
        "bankroll_initiale": bankroll_initiale,
        "bankroll_finale": round(bankroll, 2),
        "n_paris": len(rows),
        "roi_global": roi_global,
        "max_drawdown": round(max_drawdown, 4),
        "avg_ev": avg_ev,
        "volatilite_par_pari": volatilite,
        "sharpe_ratio": sharpe,
        "total_mise": round(total_mise, 2),
        "total_profit": round(total_profit, 2),
        "courbe": courbe,
    })
