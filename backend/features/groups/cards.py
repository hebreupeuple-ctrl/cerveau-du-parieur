"""
Features cartons : discipline des équipes (jaunes et rouges).
Calcule les moyennes pondérées sur les 5 derniers matchs.

Les cartons sont disponibles pour 100% des matchs FootyStats.
Impact : prédit la tendance à jouer physiquement, les suspensions potentielles,
et corrèle avec les marchés over/btts dans les matches tendus.
"""

import sqlite3
import math

# Même demi-vie que shots_corners pour cohérence
XI = 0.014


def calculer_features_cards(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
) -> dict:
    """
    Retourne les features de discipline pour une équipe.
    Préfixe home_ ou away_ appliqué par le pipeline.
    """
    matchs = _recuperer_matchs(conn, team_id, max_time)
    matchs_5 = matchs[:5]

    yellow_avg = _moyenne_stat(matchs_5, team_id, max_time, "yellow")
    red_avg    = _moyenne_stat(matchs_5, team_id, max_time, "red")

    # Score de discipline : rouge pénalisé 3× (suspension directe)
    if yellow_avg is not None and red_avg is not None:
        discipline_score = round(yellow_avg + 3.0 * red_avg, 3)
    elif yellow_avg is not None:
        discipline_score = yellow_avg
    else:
        discipline_score = None

    return {
        "yellow_cards_avg_5m":  yellow_avg,
        "red_cards_avg_5m":     red_avg,
        "discipline_score_5m":  discipline_score,
    }


def _recuperer_matchs(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
    limite: int = 5,
) -> list:
    cursor = conn.execute(
        """
        SELECT
            m.match_timestamp,
            m.home_team_id,
            m.home_yellow_cards,
            m.away_yellow_cards,
            m.home_red_cards,
            m.away_red_cards
        FROM matches m
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.match_timestamp < ?
        AND m.status = 'complete'
        AND m.home_goals IS NOT NULL
        ORDER BY m.match_timestamp DESC
        LIMIT ?
        """,
        (team_id, team_id, max_time, limite),
    )
    return cursor.fetchall()


def _moyenne_stat(
    matchs: list,
    team_id: int,
    max_time: int,
    stat: str,
) -> float | None:
    if not matchs:
        return None
    total = 0.0
    poids_total = 0.0
    for m in matchs:
        jours = (max_time - m["match_timestamp"]) / 86400
        poids = math.exp(-XI * jours)
        est_dom = m["home_team_id"] == team_id

        if stat == "yellow":
            val = m["home_yellow_cards"] if est_dom else m["away_yellow_cards"]
        elif stat == "red":
            val = m["home_red_cards"] if est_dom else m["away_red_cards"]
        else:
            val = None

        if val is not None:
            total += float(val) * poids
            poids_total += poids

    if poids_total == 0:
        return None
    return round(total / poids_total, 3)
