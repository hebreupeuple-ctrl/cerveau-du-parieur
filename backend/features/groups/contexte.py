"""
Features contextuelles du match.
"""

import sqlite3
import time


def calculer_features_contexte(
    conn: sqlite3.Connection,
    home_team_id: int,
    away_team_id: int,
    match_timestamp: int,
    game_week: int = None,
    league_id: int = None,
) -> dict:
    """
    Calcule les features contextuelles d'un match.
    """
    saison = _obtenir_infos_saison(conn, league_id)
    total_journees = saison.get("total_rounds", 38) or 38

    game_week_norm = (
        round(game_week / total_journees, 3)
        if game_week and total_journees > 0
        else 0.5
    )

    importance = _calculer_importance(
        conn=conn,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        league_id=league_id,
        game_week=game_week,
        total_journees=total_journees,
    )

    return {
        "game_week_normalized": game_week_norm,
        "match_importance_score": importance,
        "competition_type_encoded": 1,
        "is_derby": 0,
    }


def _obtenir_infos_saison(
    conn: sqlite3.Connection,
    league_id: int,
) -> dict:
    if not league_id:
        return {}

    cursor = conn.execute(
        """
        SELECT total_rounds FROM seasons
        WHERE league_id = ? AND status = 'active'
        ORDER BY year DESC LIMIT 1
        """,
        (league_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def _calculer_importance(
    conn: sqlite3.Connection,
    home_team_id: int,
    away_team_id: int,
    league_id: int,
    game_week: int,
    total_journees: int,
) -> float:
    """
    Estime l'importance du match entre 0 et 1.
    """
    if not game_week or not total_journees:
        return 0.5

    progression = game_week / total_journees

    if progression > 0.85:
        importance_temporelle = 0.9
    elif progression > 0.70:
        importance_temporelle = 0.7
    elif progression < 0.10:
        importance_temporelle = 0.4
    else:
        importance_temporelle = 0.5

    return round(importance_temporelle, 3)
