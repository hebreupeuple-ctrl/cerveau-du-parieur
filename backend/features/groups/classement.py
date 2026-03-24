"""
Features de classement et position dans la ligue.
"""

import sqlite3


def calculer_features_classement(
    conn: sqlite3.Connection,
    home_team_id: int,
    away_team_id: int,
    league_id: int,
    max_time: int,
) -> dict:
    """
    Calcule les features de classement pour les deux équipes.
    """
    classement = _construire_classement(
        conn, league_id, max_time
    )

    if not classement:
        return {
            "home_position_normalized": 0.5,
            "home_points_gap_leader": 0,
            "home_points_gap_relegation": 0,
            "away_position_normalized": 0.5,
            "away_points_gap_leader": 0,
            "away_points_gap_relegation": 0,
            "points_gap_between_teams": 0,
        }

    n_equipes = len(classement)
    leader_points = classement[0]["points"] if classement else 0
    relégation_points = (
        classement[-4]["points"]
        if n_equipes >= 4
        else classement[-1]["points"]
    )

    home_stats = next(
        (e for e in classement if e["team_id"] == home_team_id),
        None,
    )
    away_stats = next(
        (e for e in classement if e["team_id"] == away_team_id),
        None,
    )

    home_pos = home_stats["position"] if home_stats else n_equipes // 2
    away_pos = away_stats["position"] if away_stats else n_equipes // 2
    home_pts = home_stats["points"] if home_stats else 0
    away_pts = away_stats["points"] if away_stats else 0

    home_pos_norm = (n_equipes - home_pos) / max(n_equipes - 1, 1)
    away_pos_norm = (n_equipes - away_pos) / max(n_equipes - 1, 1)

    return {
        "home_position_normalized": round(home_pos_norm, 3),
        "home_points_gap_leader": leader_points - home_pts,
        "home_points_gap_relegation": home_pts - relégation_points,
        "away_position_normalized": round(away_pos_norm, 3),
        "away_points_gap_leader": leader_points - away_pts,
        "away_points_gap_relegation": away_pts - relégation_points,
        "points_gap_between_teams": home_pts - away_pts,
    }


def _construire_classement(
    conn: sqlite3.Connection,
    league_id: int,
    max_time: int,
) -> list:
    """
    Construit le classement à partir des matchs terminés.
    """
    cursor = conn.execute(
        """
        SELECT
            home_team_id,
            away_team_id,
            home_goals,
            away_goals
        FROM matches
        WHERE league_id = ?
        AND match_timestamp < ?
        AND status = 'complete'
        AND home_goals IS NOT NULL
        """,
        (league_id, max_time),
    )
    matchs = cursor.fetchall()

    if not matchs:
        return []

    equipes = {}
    for match in matchs:
        for team_id in [match["home_team_id"], match["away_team_id"]]:
            if team_id not in equipes:
                equipes[team_id] = {"points": 0, "joues": 0}

        hg = match["home_goals"]
        ag = match["away_goals"]

        equipes[match["home_team_id"]]["joues"] += 1
        equipes[match["away_team_id"]]["joues"] += 1

        if hg > ag:
            equipes[match["home_team_id"]]["points"] += 3
        elif hg == ag:
            equipes[match["home_team_id"]]["points"] += 1
            equipes[match["away_team_id"]]["points"] += 1
        else:
            equipes[match["away_team_id"]]["points"] += 3

    classement = sorted(
        [
            {"team_id": tid, **stats}
            for tid, stats in equipes.items()
        ],
        key=lambda x: x["points"],
        reverse=True,
    )

    for i, equipe in enumerate(classement):
        equipe["position"] = i + 1

    return classement
