"""
Features de forme recente.
Calcule les statistiques des N derniers matchs d'une equipe.
"""

import sqlite3
import math
from typing import Optional

XI = 0.0065


def calculer_features_forme(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
    domicile: bool = True,
) -> dict:
    matchs = _recuperer_matchs(conn, team_id, max_time)
    features = {}

    for n in [3, 5, 10, 20]:
        matchs_n = matchs[:n]
        features[f"goals_scored_{n}m"] = _moyenne_buts_marques(matchs_n, team_id, max_time)
        features[f"goals_conceded_{n}m"] = _moyenne_buts_encaisses(matchs_n, team_id, max_time)
        features[f"over25_rate_{n}m"] = _taux_over25(matchs_n)
        features[f"btts_rate_{n}m"] = _taux_btts(matchs_n)
        features[f"ppm_{n}m"] = _points_par_match(matchs_n, team_id)

    matchs_10 = matchs[:10]
    matchs_5 = matchs[:5]

    features["clean_sheet_rate_10m"] = _taux_clean_sheet(matchs_10, team_id)
    features["xg_generated_5m"] = _moyenne_xg_genere(matchs_5, team_id)
    features["xg_conceded_5m"] = _moyenne_xg_concede(matchs_5, team_id)
    features["xg_diff_5m"] = round(
        (features["xg_generated_5m"] or 0) - (features["xg_conceded_5m"] or 0),
        3,
    )
    features["win_streak"] = _serie_victoires(matchs, team_id)
    features["momentum_score"] = _score_momentum(matchs_10, team_id, max_time)
    features["rest_days"] = _jours_repos(conn, team_id, max_time)
    features["matches_last_14"] = _matchs_14_jours(matchs, max_time)

    return features


def _recuperer_matchs(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
    limite: int = 20,
) -> list:
    cursor = conn.execute(
        """
        SELECT
            m.id,
            m.match_timestamp,
            m.home_team_id,
            m.away_team_id,
            m.home_goals,
            m.away_goals,
            m.total_goals,
            m.over25,
            m.btts,
            m.home_xg,
            m.away_xg,
            m.result_1x2
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


def _moyenne_buts_marques(matchs: list, team_id: int, max_time: int) -> float:
    if not matchs:
        return 0.0
    total = 0.0
    poids_total = 0.0
    for m in matchs:
        jours = (max_time - m["match_timestamp"]) / 86400
        poids = math.exp(-XI * jours)
        est_dom = m["home_team_id"] == team_id
        buts = m["home_goals"] if est_dom else m["away_goals"]
        total += (buts or 0) * poids
        poids_total += poids
    if poids_total == 0:
        return 0.0
    return round(total / poids_total, 3)


def _moyenne_buts_encaisses(matchs: list, team_id: int, max_time: int) -> float:
    if not matchs:
        return 0.0
    total = 0.0
    poids_total = 0.0
    for m in matchs:
        jours = (max_time - m["match_timestamp"]) / 86400
        poids = math.exp(-XI * jours)
        est_dom = m["home_team_id"] == team_id
        buts = m["away_goals"] if est_dom else m["home_goals"]
        total += (buts or 0) * poids
        poids_total += poids
    if poids_total == 0:
        return 0.0
    return round(total / poids_total, 3)


def _moyenne_xg_genere(matchs: list, team_id: int) -> float:
    if not matchs:
        return 0.0
    valeurs = []
    for m in matchs:
        est_dom = m["home_team_id"] == team_id
        xg = m["home_xg"] if est_dom else m["away_xg"]
        if xg is not None:
            valeurs.append(float(xg))
    if not valeurs:
        return 0.0
    return round(sum(valeurs) / len(valeurs), 3)


def _moyenne_xg_concede(matchs: list, team_id: int) -> float:
    if not matchs:
        return 0.0
    valeurs = []
    for m in matchs:
        est_dom = m["home_team_id"] == team_id
        xg = m["away_xg"] if est_dom else m["home_xg"]
        if xg is not None:
            valeurs.append(float(xg))
    if not valeurs:
        return 0.0
    return round(sum(valeurs) / len(valeurs), 3)


def _taux_over25(matchs: list) -> float:
    if not matchs:
        return 0.0
    count = 0
    for m in matchs:
        if m["over25"] == 1:
            count += 1
        elif m["total_goals"] is not None and m["total_goals"] > 2:
            count += 1
    return round(count / len(matchs), 3)


def _taux_btts(matchs: list) -> float:
    if not matchs:
        return 0.0
    count = 0
    for m in matchs:
        if m["btts"] == 1:
            count += 1
        elif m["home_goals"] is not None and m["away_goals"] is not None:
            if m["home_goals"] > 0 and m["away_goals"] > 0:
                count += 1
    return round(count / len(matchs), 3)


def _taux_clean_sheet(matchs: list, team_id: int) -> float:
    if not matchs:
        return 0.0
    count = 0
    for m in matchs:
        est_dom = m["home_team_id"] == team_id
        buts_encaisses = m["away_goals"] if est_dom else m["home_goals"]
        if buts_encaisses is not None and buts_encaisses == 0:
            count += 1
    return round(count / len(matchs), 3)


def _points_par_match(matchs: list, team_id: int) -> float:
    if not matchs:
        return 0.0
    total = 0
    for m in matchs:
        est_dom = m["home_team_id"] == team_id
        hg = m["home_goals"] or 0
        ag = m["away_goals"] or 0
        if est_dom:
            if hg > ag:
                total += 3
            elif hg == ag:
                total += 1
        else:
            if ag > hg:
                total += 3
            elif ag == hg:
                total += 1
    return round(total / len(matchs), 3)


def _serie_victoires(matchs: list, team_id: int) -> int:
    serie = 0
    for m in matchs:
        est_dom = m["home_team_id"] == team_id
        hg = m["home_goals"] or 0
        ag = m["away_goals"] or 0
        gagne = (est_dom and hg > ag) or (not est_dom and ag > hg)
        if gagne:
            serie += 1
        else:
            break
    return serie


def _score_momentum(matchs: list, team_id: int, max_time: int) -> float:
    if not matchs:
        return 0.5
    score = 0.0
    poids_total = 0.0
    for m in matchs:
        jours = (max_time - m["match_timestamp"]) / 86400
        poids = math.exp(-XI * jours)
        est_dom = m["home_team_id"] == team_id
        hg = m["home_goals"] or 0
        ag = m["away_goals"] or 0
        if est_dom:
            pts = 3 if hg > ag else (1 if hg == ag else -1)
        else:
            pts = 3 if ag > hg else (1 if ag == hg else -1)
        score += pts * poids
        poids_total += poids
    if poids_total == 0:
        return 0.5
    # Normalise [-3, +3] → [0, 1] (score/poids_total ∈ [-3, 3], divise par 6 puis +0.5)
    score_norm = (score / poids_total) / 6.0 + 0.5
    return round(max(0.0, min(1.0, score_norm)), 3)


def _jours_repos(
    conn: sqlite3.Connection,
    team_id: int,
    max_time: int,
) -> int:
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
        return 7
    jours = (max_time - row["match_timestamp"]) // 86400
    return min(int(jours), 30)


def _matchs_14_jours(matchs: list, max_time: int) -> int:
    limite = max_time - (14 * 86400)
    return sum(1 for m in matchs if m["match_timestamp"] >= limite)
