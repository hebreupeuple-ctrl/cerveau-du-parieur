"""
Features Head-to-Head (face à face).
"""

import sqlite3


def calculer_features_h2h(
    conn: sqlite3.Connection,
    home_team_id: int,
    away_team_id: int,
    max_time: int,
    n: int = 5,
) -> dict:
    """
    Calcule les features H2H entre deux équipes.
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

    home_wins = 0
    draws = 0
    away_wins = 0
    total_goals = 0
    btts_count = 0
    over25_count = 0

    for match in matchs:
        hg = match["home_goals"] or 0
        ag = match["away_goals"] or 0
        tg = hg + ag

        est_home_domicile = match["home_team_id"] == home_team_id

        if hg > ag:
            if est_home_domicile:
                home_wins += 1
            else:
                away_wins += 1
        elif hg < ag:
            if est_home_domicile:
                away_wins += 1
            else:
                home_wins += 1
        else:
            draws += 1

        total_goals += tg
        if hg > 0 and ag > 0:
            btts_count += 1
        if tg > 2:
            over25_count += 1

    n_matchs = len(matchs)
    dominance = (home_wins - away_wins) / n_matchs

    return {
        "h2h_home_wins_5": home_wins,
        "h2h_draws_5": draws,
        "h2h_away_wins_5": away_wins,
        "h2h_goals_avg_5": round(total_goals / n_matchs, 3),
        "h2h_btts_rate_5": round(btts_count / n_matchs, 3),
        "h2h_over25_rate_5": round(over25_count / n_matchs, 3),
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
