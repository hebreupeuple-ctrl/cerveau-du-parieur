"""
Features physiques : tirs, corners, possession et mi-temps.
Calcule les statistiques sur les 5 derniers matchs avec décroissance temporelle.
"""

import sqlite3
import math

# Demi-vie ≈ 7 semaines — plus réactif que les features de forme
XI = 0.014


def calculer_features_shots_corners(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
) -> dict:
    """
    Retourne les features physiques pour une équipe.
    Préfixe home_ ou away_ appliqué par le pipeline.

    Retourne None pour les stats physiques quand aucune donnée de tirs/corners
    n'est disponible dans les matchs récents (ligue sans ces statistiques).
    Le pipeline stockera alors NULL en base, et le flag has_physical_data sera 0.
    """
    matchs = _recuperer_matchs(conn, team_id, max_time)
    matchs_5 = matchs[:5]

    shots = _moyenne_stat(matchs_5, team_id, max_time, "shots")
    shots_ot = _moyenne_stat(matchs_5, team_id, max_time, "shots_on_target")
    buts = _moyenne_buts(matchs_5, team_id, max_time)

    # Dériver conversion/efficiency seulement si leurs inputs sont disponibles
    conversion = round(buts / shots_ot, 3) if shots_ot is not None and shots_ot > 0 else None
    shot_eff = round(shots_ot / shots, 3) if shots is not None and shots > 0 else None

    ht_rates = _taux_resultats_ht(matchs_5, team_id)

    features = {
        "shots_avg_5m":            shots,
        "shots_on_target_avg_5m":  shots_ot,
        "corners_avg_5m":          _moyenne_stat(matchs_5, team_id, max_time, "corners"),
        "possession_avg_5m":       _moyenne_stat(matchs_5, team_id, max_time, "possession"),
        "goals_ht_avg_5m":         _moyenne_stat(matchs_5, team_id, max_time, "goals_ht"),
        "over15_ht_rate_5m":       _taux_over15_ht(matchs_5, team_id),
        "ht_win_rate_5m":          ht_rates["win"],
        "ht_draw_rate_5m":         ht_rates["draw"],
        "conversion_rate_5m":      conversion,
        "shot_efficiency_5m":      shot_eff,
        "fatigue_score":           _calculer_fatigue(conn, team_id, max_time),
    }

    return features


def _recuperer_matchs(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
    limite: int = 10,
) -> list:
    cursor = conn.execute(
        """
        SELECT
            m.match_timestamp,
            m.home_team_id,
            m.home_goals,
            m.away_goals,
            m.home_goals_ht,
            m.away_goals_ht,
            m.home_shots,
            m.away_shots,
            m.home_shots_on_target,
            m.away_shots_on_target,
            m.home_corners,
            m.away_corners,
            m.home_possession,
            m.away_possession
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
    """
    Retourne la moyenne pondérée de la stat sur les matchs fournis.
    Retourne None (pas 0.0) quand aucune donnée n'est disponible,
    pour distinguer "donnée absente" de "vraiment 0".
    """
    if not matchs:
        return None
    total = 0.0
    poids_total = 0.0
    for m in matchs:
        jours = (max_time - m["match_timestamp"]) / 86400
        poids = math.exp(-XI * jours)
        est_dom = m["home_team_id"] == team_id

        if stat == "shots":
            val = m["home_shots"] if est_dom else m["away_shots"]
        elif stat == "shots_on_target":
            val = m["home_shots_on_target"] if est_dom else m["away_shots_on_target"]
        elif stat == "corners":
            val = m["home_corners"] if est_dom else m["away_corners"]
        elif stat == "possession":
            val = m["home_possession"] if est_dom else m["away_possession"]
        elif stat == "goals_ht":
            val = m["home_goals_ht"] if est_dom else m["away_goals_ht"]
        else:
            val = None

        if val is not None:
            total += float(val) * poids
            poids_total += poids

    if poids_total == 0:
        return None
    return round(total / poids_total, 3)


def _moyenne_buts(matchs: list, team_id: int, max_time: int) -> float:
    if not matchs:
        return 0.0
    total = 0.0
    poids_total = 0.0
    for m in matchs:
        jours = (max_time - m["match_timestamp"]) / 86400
        poids = math.exp(-XI * jours)
        est_dom = m["home_team_id"] == team_id
        buts = m["home_goals"] if est_dom else m["away_goals"]
        if buts is not None:
            total += float(buts) * poids
            poids_total += poids
    if poids_total == 0:
        return 0.0
    return total / poids_total


def _taux_over15_ht(matchs: list, team_id: int) -> float | None:
    """
    Retourne None si aucun match avec données HT disponible
    (cohérent avec le retour None des autres stats physiques).
    """
    if not matchs:
        return None
    count = 0
    valides = 0
    for m in matchs:
        hg_ht = m["home_goals_ht"]
        ag_ht = m["away_goals_ht"]
        if hg_ht is not None and ag_ht is not None:
            valides += 1
            if (hg_ht + ag_ht) > 1:
                count += 1
    if valides == 0:
        return None
    return round(count / valides, 3)


def _taux_resultats_ht(matchs: list, team_id: int) -> dict:
    """
    Retourne le taux de victoire et de nul à la mi-temps pour l'équipe.
    Retourne None si aucun match avec données HT.
    """
    if not matchs:
        return {"win": None, "draw": None}
    wins = 0
    draws = 0
    valides = 0
    for m in matchs:
        hg_ht = m["home_goals_ht"]
        ag_ht = m["away_goals_ht"]
        if hg_ht is None or ag_ht is None:
            continue
        valides += 1
        est_dom = m["home_team_id"] == team_id
        if est_dom:
            if hg_ht > ag_ht:
                wins += 1
            elif hg_ht == ag_ht:
                draws += 1
        else:
            if ag_ht > hg_ht:
                wins += 1
            elif hg_ht == ag_ht:
                draws += 1
    if valides == 0:
        return {"win": None, "draw": None}
    return {
        "win": round(wins / valides, 3),
        "draw": round(draws / valides, 3),
    }


def _calculer_fatigue(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
) -> float:
    """
    Score de fatigue composite [0, 1].
    Combine jours de repos (0 = reposé) et densité sur 21 jours.
    """
    cursor = conn.execute(
        """
        SELECT match_timestamp FROM matches
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND match_timestamp < ?
        AND status = 'complete'
        ORDER BY match_timestamp DESC
        LIMIT 1
        """,
        (team_id, team_id, max_time),
    )
    row = cursor.fetchone()
    if not row:
        return 0.0

    jours_repos = (max_time - row["match_timestamp"]) / 86400
    # Score repos : 1 si < 3j, décroit à 0 sur 7j
    score_repos = max(0.0, 1.0 - jours_repos / 7.0)

    # Matchs dans les 21 derniers jours
    limite_21j = max_time - 21 * 86400
    cursor2 = conn.execute(
        """
        SELECT COUNT(*) FROM matches
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND match_timestamp BETWEEN ? AND ?
        AND status = 'complete'
        """,
        (team_id, team_id, limite_21j, max_time),
    )
    matchs_21j = cursor2.fetchone()[0] or 0
    # Score densité : 1 si >= 5 matchs en 21j
    score_densite = min(1.0, matchs_21j / 5.0)

    return round(0.6 * score_repos + 0.4 * score_densite, 3)
