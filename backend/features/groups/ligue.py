"""
Features de contexte de ligue.
"""

import sqlite3


def calculer_features_ligue(
    conn: sqlite3.Connection,
    league_id: int,
    max_time: int,
) -> dict:
    """
    Calcule les moyennes et statistiques de la ligue.
    """
    stats = _calculer_stats_ligue(conn, league_id, max_time)

    return {
        "league_goals_avg": stats.get("goals_avg", 2.5),
        "league_btts_rate": stats.get("btts_rate", 0.50),
        "league_over25_rate": stats.get("over25_rate", 0.55),
        "league_volatility": stats.get("volatility", 1.0),
    }


def _calculer_stats_ligue(
    conn: sqlite3.Connection,
    league_id: int,
    max_time: int,
) -> dict:
    cursor = conn.execute(
        """
        SELECT
            AVG(CAST(total_goals AS FLOAT)) as goals_avg,
            AVG(CAST(btts AS FLOAT)) as btts_rate,
            AVG(CAST(over25 AS FLOAT)) as over25_rate,
            COUNT(*) as n_matchs
        FROM matches
        WHERE league_id = ?
        AND match_timestamp < ?
        AND status = 'complete'
        AND total_goals IS NOT NULL
        """,
        (league_id, max_time),
    )
    row = cursor.fetchone()

    if not row or not row["goals_avg"]:
        return {}

    volatilite = _calculer_volatilite(
        conn, league_id, max_time, row["goals_avg"]
    )

    return {
        "goals_avg": round(row["goals_avg"], 3),
        "btts_rate": round(row["btts_rate"] or 0, 3),
        "over25_rate": round(row["over25_rate"] or 0, 3),
        "volatility": round(volatilite, 3),
    }


def _calculer_volatilite(
    conn: sqlite3.Connection,
    league_id: int,
    max_time: int,
    moyenne: float,
) -> float:
    cursor = conn.execute(
        """
        SELECT total_goals FROM matches
        WHERE league_id = ?
        AND match_timestamp < ?
        AND status = 'complete'
        AND total_goals IS NOT NULL
        LIMIT 200
        """,
        (league_id, max_time),
    )
    buts = [row["total_goals"] for row in cursor.fetchall()]

    if len(buts) < 5:
        return 1.0

    variance = sum((b - moyenne) ** 2 for b in buts) / len(buts)
    return variance ** 0.5
