"""
Features Head-to-Head (face à face).
"""

import math
import sqlite3

# Demi-vie 1.5 ans : un match vieux de 3 ans pèse ~25% d'un match récent
_DECAY_HALFLIFE_DAYS = 547.5


def calculer_features_h2h(
    conn: sqlite3.Connection,
    home_team_id: int,
    away_team_id: int,
    max_time: int,
    n: int = 5,
) -> dict:
    """
    Calcule les features H2H entre deux équipes avec decay temporel exponentiel.
    Les matchs récents ont plus de poids que les matchs anciens.
    """
    matchs = _recuperer_h2h(
        conn, home_team_id, away_team_id, max_time, n
    )

    if not matchs:
        return {
            "h2h_home_wins_5": 0,
            "h2h_draws_5": 0,
            "h2h_away_wins_5": 0,
            "h2h_goals_avg_5": 0.0,
            "h2h_btts_rate_5": 0.0,
            "h2h_over25_rate_5": 0.0,
            "h2h_dominance_score": 0.0,
        }

    home_wins = 0.0
    draws = 0.0
    away_wins = 0.0
    total_goals = 0.0
    btts_count = 0.0
    over25_count = 0.0
    total_weight = 0.0

    for match in matchs:
        hg = match["home_goals"] or 0
        ag = match["away_goals"] or 0
        tg = hg + ag

        days_ago = max(0.0, (max_time - (match["match_timestamp"] or max_time)) / 86400.0)
        weight = math.exp(-math.log(2) * days_ago / _DECAY_HALFLIFE_DAYS)

        est_home_domicile = match["home_team_id"] == home_team_id

        if hg > ag:
            if est_home_domicile:
                home_wins += weight
            else:
                away_wins += weight
        elif hg < ag:
            if est_home_domicile:
                away_wins += weight
            else:
                home_wins += weight
        else:
            draws += weight

        total_goals += tg * weight
        if hg > 0 and ag > 0:
            btts_count += weight
        if tg > 2:
            over25_count += weight

        total_weight += weight

    if total_weight == 0.0:
        total_weight = 1.0

    dominance = (home_wins - away_wins) / total_weight

    return {
        "h2h_home_wins_5": round(home_wins, 3),
        "h2h_draws_5": round(draws, 3),
        "h2h_away_wins_5": round(away_wins, 3),
        "h2h_goals_avg_5": round(total_goals / total_weight, 3),
        "h2h_btts_rate_5": round(btts_count / total_weight, 3),
        "h2h_over25_rate_5": round(over25_count / total_weight, 3),
        "h2h_dominance_score": round(dominance, 3),
    }


def _recuperer_h2h(
    conn: sqlite3.Connection,
    home_team_id: int,
    away_team_id: int,
    max_time: int,
    n: int,
) -> list:
    cursor = conn.execute(
        """
        SELECT
            home_team_id, away_team_id,
            home_goals, away_goals,
            total_goals, btts, over25,
            match_timestamp
        FROM matches
        WHERE (
            (home_team_id = ? AND away_team_id = ?)
            OR
            (home_team_id = ? AND away_team_id = ?)
        )
        AND match_timestamp < ?
        AND status = 'complete'
        AND home_goals IS NOT NULL
        ORDER BY match_timestamp DESC
        LIMIT ?
        """,
        (
            home_team_id, away_team_id,
            away_team_id, home_team_id,
            max_time, n,
        ),
    )
    return cursor.fetchall()
