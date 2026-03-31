"""
Endpoint Analyse — historique complet de toutes les prédictions par match.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import sqlite3

from backend.api.dependencies import get_db, get_current_user

router = APIRouter()

MARKET_LABELS = {
    "over15":    "Plus de 1.5 buts",
    "over25":    "Plus de 2.5 buts",
    "over35":    "Plus de 3.5 buts",
    "over45":    "Plus de 4.5 buts",
    "btts":      "Les deux équipes marquent",
    "over15_ht": "Plus de 1.5 buts (MT)",
    "1x2_home":  "Victoire domicile",
    "1x2_draw":  "Match nul",
    "1x2_away":  "Victoire extérieur",
}


def _market_result(
    market: str,
    home_goals: int,
    away_goals: int,
    home_goals_ht: int = None,
    away_goals_ht: int = None,
) -> bool | None:
    """Retourne True/False si la prédiction était correcte, None si match non joué."""
    if home_goals is None or away_goals is None:
        return None
    total = home_goals + away_goals
    if market == "over15":    return total > 1
    if market == "over25":    return total > 2
    if market == "over35":    return total > 3
    if market == "over45":    return total > 4
    if market == "btts":      return home_goals > 0 and away_goals > 0
    if market == "under25":   return total < 3
    if market == "ng":        return home_goals == 0 and away_goals == 0
    if market == "dc_1x":     return home_goals >= away_goals
    if market == "dc_x2":     return away_goals >= home_goals
    if market == "gg_over25": return home_goals > 0 and away_goals > 0 and total > 2
    if market == "1x2_home":  return home_goals > away_goals
    if market == "1x2_draw":  return home_goals == away_goals
    if market == "1x2_away":  return away_goals > home_goals
    # Marchés mi-temps
    if home_goals_ht is None or away_goals_ht is None:
        return None
    if market == "1x2_ht_home": return home_goals_ht > away_goals_ht
    if market == "1x2_ht_draw": return home_goals_ht == away_goals_ht
    if market == "1x2_ht_away": return away_goals_ht > home_goals_ht
    if market == "over15_ht":   return (home_goals_ht + away_goals_ht) > 1
    return None


@router.get("/matches")
async def analyse_matches(
    mode: str = Query("all", pattern="^(all|upcoming|past)$"),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retourne tous les matchs ayant au moins un pronostic,
    avec l'ensemble des prédictions par marché.
    Inclut l'historique complet (matchs joués + à venir).
    """
    offset = (page - 1) * limit
    user_id = current_user["id"]

    # Clauses de filtre
    where_parts = ["p.user_id = ?"]
    params: list = [user_id]

    if mode == "upcoming":
        where_parts.append("m.status IN ('upcoming', 'live')")
    elif mode == "past":
        where_parts.append("m.status = 'complete'")

    if search:
        where_parts.append(
            "(t1.name LIKE ? OR t2.name LIKE ? OR l.name LIKE ?)"
        )
        s = f"%{search}%"
        params += [s, s, s]

    where_sql = " AND ".join(where_parts)

    # Compter les matchs distincts
    total_matchs = conn.execute(
        f"""
        SELECT COUNT(DISTINCT p.match_id)
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        JOIN leagues l ON m.league_id = l.id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()[0]

    # Récupérer les match_ids paginés (triés par date desc)
    match_ids = conn.execute(
        f"""
        SELECT DISTINCT p.match_id, m.match_timestamp
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        JOIN leagues l ON m.league_id = l.id
        WHERE {where_sql}
        ORDER BY m.match_timestamp DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    if not match_ids:
        return JSONResponse(content={
            "success": True,
            "data": {
                "items": [],
                "pagination": {
                    "total": total_matchs,
                    "page": page,
                    "limit": limit,
                    "pages": max(1, (total_matchs + limit - 1) // limit),
                },
            },
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        })

    ids = [r["match_id"] for r in match_ids]
    placeholders = ",".join("?" * len(ids))

    # Récupérer tous les pronostics pour ces matchs
    rows = conn.execute(
        f"""
        SELECT
            p.match_id,
            p.market,
            p.model_probability,
            p.bookmaker_probability,
            p.probability_edge,
            p.expected_value,
            p.confidence_score,
            p.reference_odds,
            p.reference_bookmaker,
            p.status         AS pronostic_status,
            p.actual_stake,
            p.actual_odds,
            p.actual_profit,
            p.recommended_stake,
            m.match_timestamp,
            m.status         AS match_status,
            m.home_goals,
            m.away_goals,
            m.home_goals_ht,
            m.away_goals_ht,
            t1.name          AS home_team,
            t2.name          AS away_team,
            l.name           AS league_name
        FROM pronostics p
        JOIN matches m  ON p.match_id = m.id
        JOIN teams t1   ON m.home_team_id = t1.id
        JOIN teams t2   ON m.away_team_id = t2.id
        JOIN leagues l  ON m.league_id = l.id
        WHERE p.match_id IN ({placeholders})
        AND p.user_id = ?
        ORDER BY m.match_timestamp DESC, p.confidence_score DESC
        """,
        ids + [user_id],
    ).fetchall()

    # Grouper par match
    matchs: dict = {}
    for r in rows:
        mid = r["match_id"]
        if mid not in matchs:
            matchs[mid] = {
                "match_id": mid,
                "home_team": r["home_team"],
                "away_team": r["away_team"],
                "league": r["league_name"],
                "kickoff_timestamp": r["match_timestamp"],
                "match_status": r["match_status"],
                "score": (
                    f"{r['home_goals']}-{r['away_goals']}"
                    if r["home_goals"] is not None and r["away_goals"] is not None
                    else None
                ),
                "markets": [],
            }

        # Résultat réel du marché
        correct = _market_result(
            r["market"],
            r["home_goals"],
            r["away_goals"],
            r["home_goals_ht"],
            r["away_goals_ht"],
        )

        matchs[mid]["markets"].append({
            "market": r["market"],
            "label": MARKET_LABELS.get(r["market"], r["market"]),
            "model_probability": r["model_probability"],
            "bookmaker_probability": r["bookmaker_probability"],
            "probability_edge": r["probability_edge"],
            "expected_value": r["expected_value"],
            "confidence_score": r["confidence_score"],
            "reference_odds": r["reference_odds"],
            "reference_bookmaker": r["reference_bookmaker"],
            "pronostic_status": r["pronostic_status"],
            "actual_stake": r["actual_stake"],
            "actual_odds": r["actual_odds"],
            "actual_profit": r["actual_profit"],
            "recommended_stake": r["recommended_stake"],
            "prediction_correct": correct,
        })

    items = list(matchs.values())

    return JSONResponse(content={
        "success": True,
        "data": {
            "items": items,
            "pagination": {
                "total": total_matchs,
                "page": page,
                "limit": limit,
                "pages": max(1, (total_matchs + limit - 1) // limit),
            },
        },
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    })
