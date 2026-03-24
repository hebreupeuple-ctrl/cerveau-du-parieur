"""
Modèle Dixon-Coles pour la prédiction de buts.
Estime les forces d'attaque et de défense de chaque équipe.
"""

import math
import sqlite3
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion

logger = get_logger(__name__)

XI = 0.0065
RHO = -0.13


def correction_rho(
    home_goals: int,
    away_goals: int,
    lambda_val: float,
    mu_val: float,
    rho: float,
) -> float:
    """
    Facteur de correction Dixon-Coles pour les scores faibles.
    Appliqué uniquement sur 0-0, 1-0, 0-1, 1-1.
    """
    if home_goals == 0 and away_goals == 0:
        return 1 - lambda_val * mu_val * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + away_goals * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + home_goals * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    else:
        return 1.0


def poisson_prob(k: int, lambda_val: float) -> float:
    """Calcule P(X=k) pour une loi de Poisson."""
    if lambda_val <= 0:
        return 1.0 if k == 0 else 0.0
    try:
        return math.exp(-lambda_val) * (lambda_val ** k) / math.factorial(k)
    except (OverflowError, ValueError):
        return 0.0


def calculer_matrice_scores(
    lambda_val: float,
    mu_val: float,
    rho: float = RHO,
    max_goals: int = 8,
) -> dict:
    """
    Calcule la matrice complète des probabilités de scores.
    Retourne un dict {"home_goals-away_goals": probabilite}.
    """
    matrice = {}

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p_home = poisson_prob(i, lambda_val)
            p_away = poisson_prob(j, mu_val)
            correction = correction_rho(i, j, lambda_val, mu_val, rho)
            matrice[f"{i}-{j}"] = p_home * p_away * correction

    total = sum(matrice.values())
    if total > 0:
        matrice = {k: v / total for k, v in matrice.items()}

    return matrice


def deriver_probabilites_marches(matrice: dict) -> dict:
    """
    Dérive toutes les probabilités des marchés
    depuis la matrice des scores.
    """
    prob_home_win = 0.0
    prob_draw = 0.0
    prob_away_win = 0.0
    prob_over15 = 0.0
    prob_over25 = 0.0
    prob_over35 = 0.0
    prob_over45 = 0.0
    prob_btts = 0.0
    prob_gg_over25 = 0.0
    prob_gg_under25 = 0.0

    for score, prob in matrice.items():
        parts = score.split("-")
        hg = int(parts[0])
        ag = int(parts[1])
        tg = hg + ag

        if hg > ag:
            prob_home_win += prob
        elif hg == ag:
            prob_draw += prob
        else:
            prob_away_win += prob

        if tg > 1:
            prob_over15 += prob
        if tg > 2:
            prob_over25 += prob
        if tg > 3:
            prob_over35 += prob
        if tg > 4:
            prob_over45 += prob

        if hg > 0 and ag > 0:
            prob_btts += prob
            if tg > 2:
                prob_gg_over25 += prob
            else:
                prob_gg_under25 += prob

    score_plus_probable = max(matrice, key=matrice.get)
    prob_score_plus_probable = matrice[score_plus_probable]

    return {
        "prob_home_win": round(prob_home_win, 4),
        "prob_draw": round(prob_draw, 4),
        "prob_away_win": round(prob_away_win, 4),
        "prob_over15": round(prob_over15, 4),
        "prob_over25": round(prob_over25, 4),
        "prob_over35": round(prob_over35, 4),
        "prob_over45": round(prob_over45, 4),
        "prob_btts": round(prob_btts, 4),
        "prob_btts_no": round(1 - prob_btts, 4),
        "prob_gg_over25": round(prob_gg_over25, 4),
        "prob_gg_under25": round(prob_gg_under25, 4),
        "most_likely_score": score_plus_probable,
        "most_likely_score_prob": round(prob_score_plus_probable, 4),
    }


class DixonColesModel:
    """
    Modèle Dixon-Coles complet.
    Estime les paramètres de force par équipe
    et prédit les distributions de scores.
    """

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()
        self.home_advantage = 1.20
        self.rho = RHO

    def predire_match(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        max_time: int,
    ) -> Optional[dict]:
        """
        Prédit les probabilités pour un match.
        """
        try:
            params_home = self._obtenir_parametres_equipe(
                home_team_id, league_id, max_time
            )
            params_away = self._obtenir_parametres_equipe(
                away_team_id, league_id, max_time
            )
            home_adv = self._calculer_avantage_domicile(league_id, max_time)

            lambda_val = (
                params_home["attack_home"]
                * params_away["defense_away"]
                * home_adv
            )
            mu_val = (
                params_away["attack_away"]
                * params_home["defense_home"]
            )

            lambda_val = max(0.1, min(lambda_val, 8.0))
            mu_val = max(0.1, min(mu_val, 8.0))

            matrice = calculer_matrice_scores(
                lambda_val=lambda_val,
                mu_val=mu_val,
                rho=self.rho,
            )

            probabilites = deriver_probabilites_marches(matrice)
            probabilites["dc_lambda"] = round(lambda_val, 4)
            probabilites["dc_mu"] = round(mu_val, 4)
            probabilites["score_matrix"] = matrice

            return probabilites

        except Exception as e:
            logger.error_ctx(
                "Erreur prédiction Dixon-Coles",
                context={
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "erreur": str(e),
                },
            )
            return None

    def _obtenir_parametres_equipe(
        self,
        team_id: int,
        league_id: int,
        max_time: int,
        n_matchs: int = 20,
    ) -> dict:
        """
        Calcule les paramètres de force d'une équipe
        basés sur ses performances récentes.
        """
        cursor = self.conn.execute(
            """
            SELECT
                home_team_id, away_team_id,
                home_goals, away_goals,
                match_timestamp
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND league_id = ?
            AND match_timestamp < ?
            AND status = 'complete'
            AND home_goals IS NOT NULL
            ORDER BY match_timestamp DESC
            LIMIT ?
            """,
            (team_id, team_id, league_id, max_time, n_matchs),
        )
        matchs = cursor.fetchall()

        if not matchs:
            return {
                "attack_home": 1.0,
                "attack_away": 1.0,
                "defense_home": 1.0,
                "defense_away": 1.0,
            }

        moy_ligue = self._moyenne_buts_ligue(league_id, max_time)
        moy_dom = moy_ligue.get("home", 1.5)
        moy_ext = moy_ligue.get("away", 1.2)

        buts_marques_dom = []
        buts_encaisses_dom = []
        buts_marques_ext = []
        buts_encaisses_ext = []
        poids = []

        for i, match in enumerate(matchs):
            w = math.exp(
                -XI * (max_time - match["match_timestamp"]) / 86400
            )
            est_dom = match["home_team_id"] == team_id
            hg = match["home_goals"] or 0
            ag = match["away_goals"] or 0

            if est_dom:
                buts_marques_dom.append((hg, w))
                buts_encaisses_dom.append((ag, w))
            else:
                buts_marques_ext.append((ag, w))
                buts_encaisses_ext.append((hg, w))

        def moyenne_ponderee(valeurs):
            if not valeurs:
                return None
            total = sum(v * w for v, w in valeurs)
            poids_total = sum(w for _, w in valeurs)
            return total / poids_total if poids_total > 0 else None

        moy_m_dom = moyenne_ponderee(buts_marques_dom) or moy_dom
        moy_e_dom = moyenne_ponderee(buts_encaisses_dom) or moy_ext
        moy_m_ext = moyenne_ponderee(buts_marques_ext) or moy_ext
        moy_e_ext = moyenne_ponderee(buts_encaisses_ext) or moy_dom

        attack_home = moy_m_dom / max(moy_dom, 0.1)
        defense_home = moy_e_dom / max(moy_ext, 0.1)
        attack_away = moy_m_ext / max(moy_ext, 0.1)
        defense_away = moy_e_ext / max(moy_dom, 0.1)

        return {
            "attack_home": round(max(0.1, min(attack_home, 5.0)), 4),
            "attack_away": round(max(0.1, min(attack_away, 5.0)), 4),
            "defense_home": round(max(0.1, min(defense_home, 5.0)), 4),
            "defense_away": round(max(0.1, min(defense_away, 5.0)), 4),
        }

    def _moyenne_buts_ligue(
        self,
        league_id: int,
        max_time: int,
    ) -> dict:
        """Calcule la moyenne de buts domicile et extérieur de la ligue."""
        cursor = self.conn.execute(
            """
            SELECT
                AVG(CAST(home_goals AS FLOAT)) as avg_home,
                AVG(CAST(away_goals AS FLOAT)) as avg_away
            FROM matches
            WHERE league_id = ?
            AND match_timestamp < ?
            AND status = 'complete'
            AND home_goals IS NOT NULL
            """,
            (league_id, max_time),
        )
        row = cursor.fetchone()
        return {
            "home": row["avg_home"] or 1.5,
            "away": row["avg_away"] or 1.2,
        }

    def _calculer_avantage_domicile(
        self,
        league_id: int,
        max_time: int,
    ) -> float:
        """Calcule l'avantage domicile de la ligue."""
        moyennes = self._moyenne_buts_ligue(league_id, max_time)
        avg_home = moyennes["home"]
        avg_away = moyennes["away"]

        if avg_away > 0:
            avantage = avg_home / avg_away
        else:
            avantage = 1.2

        return round(max(1.0, min(avantage, 2.0)), 4)
