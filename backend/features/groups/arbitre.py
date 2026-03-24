"""
Features liées à l'arbitre assigné au match.
Calcule buts moyens, biais domicile et volatilité à partir de l'historique.
"""

import sqlite3


def calculer_features_arbitre(
    conn: sqlite3.Connection,
    match_id: int,
    max_time: int,
) -> dict:
    """
    Calcule les features statistiques de l'arbitre assigné.
    Retourne des None si l'arbitre est inconnu ou sans historique suffisant.
    """
    cursor = conn.execute(
        "SELECT referee_id FROM matches WHERE id = ?",
        (match_id,),
    )
    row = cursor.fetchone()
    if not row or not row["referee_id"]:
        return _defaut()

    referee_id = row["referee_id"]

    cursor = conn.execute(
        """
        SELECT
            home_goals,
            away_goals,
            result_1x2
        FROM matches
        WHERE referee_id = ?
        AND match_timestamp < ?
        AND status = 'complete'
        AND home_goals IS NOT NULL
        ORDER BY match_timestamp DESC
        LIMIT 50
        """,
        (referee_id, max_time),
    )
    matchs = cursor.fetchall()

    if len(matchs) < 5:
        return _defaut()

    total_goals = [
        (m["home_goals"] or 0) + (m["away_goals"] or 0)
        for m in matchs
    ]
    n = len(matchs)

    referee_avg_goals = round(sum(total_goals) / n, 3)
    home_wins = sum(1 for m in matchs if m["result_1x2"] == "home")
    referee_home_bias = round(home_wins / n, 3)

    mean = sum(total_goals) / n
    variance = sum((g - mean) ** 2 for g in total_goals) / n
    referee_goals_volatility = round(variance ** 0.5, 3)

    return {
        "referee_avg_goals":        referee_avg_goals,
        "referee_home_bias":        referee_home_bias,
        "referee_goals_volatility": referee_goals_volatility,
    }


def _defaut() -> dict:
    return {
        "referee_avg_goals":        None,
        "referee_home_bias":        None,
        "referee_goals_volatility": None,
    }
