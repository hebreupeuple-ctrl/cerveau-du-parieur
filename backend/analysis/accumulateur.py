"""
Generateur de pronostics.
Combine Dixon-Coles, ML, Value Betting et Kelly
pour produire les recommandations finales.
"""

import sqlite3
import time
import json
from datetime import datetime, timezone
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion
from backend.models.algorithms.dixon_coles import DixonColesModel, poisson_prob
from backend.models.trainer import ModelTrainer
from backend.analysis.value_betting import analyser_match
from backend.analysis.kelly import calculer_kelly_complet
from backend.features.pipeline import FeaturePipeline

logger = get_logger(__name__)


def _prob_more_goals_half(
    lam_1st: float,
    lam_2nd: float,
    max_goals: int = 10,
) -> tuple[float, float, float]:
    """
    Calcule P(1ère MT > 2ème MT), P(égal), P(2ème MT > 1ère MT)
    en supposant buts 1ère et 2ème indépendants et distribués Poisson.
    """
    p_1st = p_eq = p_2nd = 0.0
    for g1 in range(max_goals + 1):
        for g2 in range(max_goals + 1):
            p = poisson_prob(g1, lam_1st) * poisson_prob(g2, lam_2nd)
            if g1 > g2:
                p_1st += p
            elif g1 == g2:
                p_eq += p
            else:
                p_2nd += p
    return p_1st, p_eq, p_2nd


class GenerateurPronostics:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()
        self.dc_model = DixonColesModel(self.conn)
        self.ml_trainer = ModelTrainer(self.conn)
        self.feature_pipeline = FeaturePipeline(self.conn)
        self._modeles_charges = False

    def _charger_modeles(self) -> None:
        if not self._modeles_charges:
            self.ml_trainer._charger_modeles()
            self._modeles_charges = True

    def generer_pour_match(
        self,
        match_id: int,
        user_id: int,
        bankroll: float,
        bankroll_initiale: float,
        roi_historique: Optional[float] = None,
        n_paris: int = 0,
        fraction_override: Optional[float] = None,
        marches_autorises: Optional[set[str]] = None,
    ) -> list:
        """
        Genere les pronostics pour un match specifique.
        Retourne une liste de pronostics avec valeur positive.
        """
        self._charger_modeles()

        match = self.conn.execute(
            """
            SELECT m.*, l.name as league_name
            FROM matches m
            JOIN leagues l ON m.league_id = l.id
            WHERE m.id = ?
            """,
            (match_id,),
        ).fetchone()

        if not match:
            return []

        if match["status"] != "upcoming":
            return []

        # 2h avant le coup d'envoi : laisse le temps aux vraies nouvelles
        # (blessures, compositions) de se refléter dans les cotes bookmaker
        # avant que nos features soient figées.
        max_time = match["match_timestamp"] - 7200

        features_row = self.conn.execute(
            "SELECT * FROM match_features WHERE match_id = ?",
            (match_id,),
        ).fetchone()

        # Recalcule si absent ou si calculé il y a plus de 2h (depuis maintenant)
        doit_recalculer = True
        if features_row and features_row["calculated_at"]:
            try:
                calculated_ts = int(
                    datetime.fromisoformat(
                        features_row["calculated_at"].replace("Z", "+00:00")
                    )
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
                now = int(time.time())
                # Cache valide si les features ont été calculées il y a < 2h
                if calculated_ts >= now - 2 * 3600:
                    doit_recalculer = False
            except (ValueError, TypeError):
                pass

        if doit_recalculer:
            features_dict = self.feature_pipeline.calculer_features_match(
                match_id=match_id,
                match_timestamp=match["match_timestamp"],
                home_team_id=match["home_team_id"],
                away_team_id=match["away_team_id"],
                league_id=match["league_id"],
                game_week=match["game_week"],
            )
        else:
            features_dict = dict(features_row)

        if not features_dict:
            return []

        pred_dc = self.dc_model.predire_match(
            home_team_id=match["home_team_id"],
            away_team_id=match["away_team_id"],
            league_id=match["league_id"],
            max_time=max_time,
        )

        pred_ml = {}
        if self.ml_trainer.modeles:
            pred_ml = self.ml_trainer.predire(features_dict)

        has_physical = bool(features_dict.get("has_physical_data"))
        probabilites_finales = self._fusionner_probabilites(
            pred_dc, pred_ml, has_physical_data=has_physical
        )

        if not probabilites_finales:
            return []

        matrice = pred_dc.get("score_matrix", {}) if pred_dc else {}

        cotes = self._obtenir_cotes(match_id)
        cotes_reelles = bool(cotes)

        if not cotes:
            cotes = self._generer_cotes_reference(probabilites_finales)

        opportunites = analyser_match(
            probabilites_modele=probabilites_finales,
            cotes_disponibles=cotes,
            seuil_confiance=0.30,
            cotes_reelles=cotes_reelles,
        )

        pronostics = []
        for opp in opportunites:
            if marches_autorises and opp["marche"] not in marches_autorises:
                continue

            kelly = calculer_kelly_complet(
                probabilite=opp["probabilite_modele"],
                cote=opp["cote"],
                bankroll=bankroll,
                bankroll_initiale=bankroll_initiale,
                roi_historique=roi_historique,
                n_paris=n_paris,
                fraction_override=fraction_override,
            )

            if kelly["mise_recommandee"] <= 0:
                continue

            pronostic = {
                "match_id": match_id,
                "user_id": user_id,
                "marche": opp["marche"],
                "market_label": opp["label"],
                "probabilite_modele": opp["probabilite_modele"],
                "probabilite_bookmaker": opp["probabilite_bookmaker"],
                "edge": opp["edge"],
                "cote": opp["cote"],
                "ev": opp["ev"],
                "confiance": opp["confiance"],
                "kelly_brut": kelly["kelly_brut"],
                "kelly_fraction": kelly["fraction"],
                "mise_recommandee": kelly["mise_recommandee"],
                "score_matrix": json.dumps(matrice) if matrice else None,
                "pred_dc": pred_dc,
                "pred_ml": pred_ml,
            }
            pronostics.append(pronostic)

        return pronostics

    def _fusionner_probabilites(
        self,
        pred_dc: Optional[dict],
        pred_ml: dict,
        has_physical_data: bool = False,
    ) -> dict:
        """
        Fusionne les predictions DC et ML.
        DC = 100% si ML non disponible.
        Poids ML augmentés quand les données physiques (tirs/corners/possession)
        sont disponibles — ces features rendent le ML nettement plus fiable.
        """
        if not pred_dc:
            return {}

        proba_dc = {
            "prob_home_win": pred_dc.get("prob_home_win", 0.33),
            "prob_draw": pred_dc.get("prob_draw", 0.33),
            "prob_away_win": pred_dc.get("prob_away_win", 0.33),
            "prob_over15": pred_dc.get("prob_over15", 0.70),
            "prob_over25": pred_dc.get("prob_over25", 0.50),
            "prob_over45": pred_dc.get("prob_over45", 0.15),
            "prob_btts": pred_dc.get("prob_btts", 0.50),
            "prob_btts_no": pred_dc.get("prob_btts_no", 0.50),
        }

        if not pred_ml:
            return proba_dc

        # Poids DC/ML calibrés par marché.
        # Deux tables : sans données physiques (forme seule) et avec (tirs/corners/xG disponibles).
        # Les données physiques enrichissent le signal ML et justifient une confiance accrue.
        if has_physical_data:
            POIDS_PAR_MARCHE = {
                "prob_home_win":  (0.60, 0.40),
                "prob_draw":      (0.60, 0.40),
                "prob_away_win":  (0.60, 0.40),
                "prob_over15":    (0.50, 0.50),
                "prob_over25":    (0.40, 0.60),
                "prob_over45":    (0.55, 0.45),
                "prob_btts":      (0.40, 0.60),
                "prob_btts_no":   (0.40, 0.60),
            }
        else:
            POIDS_PAR_MARCHE = {
                "prob_home_win":  (0.80, 0.20),
                "prob_draw":      (0.80, 0.20),
                "prob_away_win":  (0.80, 0.20),
                "prob_over15":    (0.65, 0.35),
                "prob_over25":    (0.55, 0.45),
                "prob_over45":    (0.75, 0.25),
                "prob_btts":      (0.55, 0.45),
                "prob_btts_no":   (0.55, 0.45),
            }

        result = {}
        for k, v_dc in proba_dc.items():
            cle_ml = f"ml_{k}"
            poids_dc, poids_ml = POIDS_PAR_MARCHE.get(k, (0.60, 0.40))
            if cle_ml in pred_ml and poids_ml > 0:
                v_ml = pred_ml[cle_ml]
                result[k] = round(
                    v_dc * poids_dc + v_ml * poids_ml, 4
                )
            else:
                result[k] = v_dc

        # Marchés mi-temps depuis ML si disponibles
        if "ml_prob_ht_home_win" in pred_ml:
            result["prob_ht_home_win"] = round(
                pred_ml["ml_prob_ht_home_win"] * 0.6
                + pred_dc.get("prob_home_win", 0.33) * 0.4, 4
            )
            result["prob_ht_draw"] = round(
                pred_ml.get("ml_prob_ht_draw", pred_dc.get("prob_draw", 0.33)) * 0.6
                + pred_dc.get("prob_draw", 0.33) * 0.4, 4
            )
            result["prob_ht_away_win"] = round(
                pred_ml.get("ml_prob_ht_away_win", pred_dc.get("prob_away_win", 0.33)) * 0.6
                + pred_dc.get("prob_away_win", 0.33) * 0.4, 4
            )

        # Marchés dérivés — calculés depuis les probabilités fusionnées
        result["prob_dc_1x"] = round(
            min(result.get("prob_home_win", 0) + result.get("prob_draw", 0), 0.99), 4
        )
        result["prob_dc_x2"] = round(
            min(result.get("prob_draw", 0) + result.get("prob_away_win", 0), 0.99), 4
        )
        # GG & Over 2.5 : approximation par indépendance (légèrement optimiste)
        result["prob_gg_over25"] = round(
            result.get("prob_btts", 0) * result.get("prob_over25", 0), 4
        )

        # Mi-temps over15 : depuis ML si disponible, sinon dérivé de over25 FT
        # Empiriquement ~55% des matchs over25 FT ont aussi over15 HT
        if "ml_prob_over15_ht" in pred_ml:
            result["prob_over15_ht"] = round(pred_ml["ml_prob_over15_ht"], 4)
        else:
            result["prob_over15_ht"] = round(result.get("prob_over25", 0.5) * 0.55, 4)

        # Marché "quelle mi-temps a le plus de buts"
        # Split empirique : ~45% des buts en 1ère MT, ~55% en 2ème MT
        lam_total = pred_dc.get("dc_lambda", 1.3) + pred_dc.get("dc_mu", 1.1)
        p_1st, p_eq, p_2nd = _prob_more_goals_half(lam_total * 0.45, lam_total * 0.55)
        result["prob_more_goals_1st"]   = round(p_1st, 4)
        result["prob_more_goals_equal"] = round(p_eq, 4)
        result["prob_more_goals_2nd"]   = round(p_2nd, 4)

        return result

    def _obtenir_cotes(self, match_id: int) -> dict:
        """
        Recupere les cotes bookmaker depuis la base.
        Prefere Pinnacle (tier 1).
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM odds
            WHERE match_id = ?
            ORDER BY bookmaker_tier ASC, collected_timestamp DESC
            LIMIT 1
            """,
            (match_id,),
        )
        row = cursor.fetchone()

        if not row:
            return {}

        return dict(row)

    def _generer_cotes_reference(
        self,
        probabilites: dict,
    ) -> dict:
        """
        Genere des cotes de reference depuis les probabilites
        quand aucune cote bookmaker n'est disponible.
        Applique une marge de 6% simulant un bookmaker compétitif.
        Avec seuil_edge=0.03, edge = prob * (1-1/1.06) ≈ prob * 0.0566
        → passe le seuil dès prob >= 0.53.
        """
        marge = 1.06

        cotes = {}

        for cle_prob, cle_cote in [
            ("prob_over15",   "odds_over15"),
            ("prob_over25",   "odds_over25"),
            ("prob_over45",   "odds_over45"),
            ("prob_btts",     "odds_btts_yes"),
            ("prob_home_win", "odds_home"),
            ("prob_draw",     "odds_draw"),
            ("prob_away_win", "odds_away"),
            ("prob_dc_1x",    "odds_dc_1x"),
            ("prob_dc_x2",    "odds_dc_x2"),
            ("prob_gg_over25", "odds_gg_over25"),
            ("prob_over15_ht", "odds_over15_ht"),
        ]:
            p = probabilites.get(cle_prob)
            if p and p > 0.05:
                cotes[cle_cote] = round(marge / p, 2)

        return cotes

    def generer_pronostics_du_jour(
        self,
        user_id: int,
        bankroll: float,
        bankroll_initiale: float,
        roi_historique: Optional[float] = None,
        n_paris: int = 0,
        fraction_override: Optional[float] = None,
        max_pronostics: int = 3,
    ) -> list:
        """
        Genere les meilleurs pronostics pour les matchs du jour.
        """
        maintenant = int(time.time())
        # Fenêtre : matchs entre 2h et 48h à venir
        # - Min 2h : laisser le temps de placer le pari
        # - Max 48h : aligné sur la collecte des cotes (heures=48)
        debut_fenetre = maintenant + (2 * 3600)
        fin_fenetre   = maintenant + (48 * 3600)
        matchs = self.conn.execute(
            """
            SELECT m.id, m.match_timestamp,
                   t1.name as home_name,
                   t2.name as away_name,
                   l.name as league_name
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            JOIN leagues l ON m.league_id = l.id
            WHERE m.status = 'upcoming'
            AND m.match_timestamp BETWEEN ? AND ?
            AND l.is_active = 1
            ORDER BY m.match_timestamp ASC
            """,
            (debut_fenetre, fin_fenetre),
        ).fetchall()

        logger.info_ctx(
            "Matchs a analyser",
            context={"count": len(matchs)},
        )

        tous_pronostics = []

        for match in matchs:
            pronostics = self.generer_pour_match(
                match_id=match["id"],
                user_id=user_id,
                bankroll=bankroll,
                bankroll_initiale=bankroll_initiale,
                roi_historique=roi_historique,
                n_paris=n_paris,
                fraction_override=fraction_override,
                marches_autorises=None,
            )
            tous_pronostics.extend(pronostics)

        tous_pronostics.sort(
            key=lambda x: x["ev"],
            reverse=True,
        )

        return tous_pronostics[:max_pronostics]

    def _obtenir_leagues_autorisees(self, user_id: int) -> set[int]:
        # Joint leagues pour exclure les ligues désactivées même si
        # user_leagues.is_active = 1 (cas d'une ligue supprimée du compte FootyStats)
        rows = self.conn.execute(
            """
            SELECT ul.league_id
            FROM user_leagues ul
            JOIN leagues l ON ul.league_id = l.id
            WHERE ul.user_id = ?
            AND ul.is_active = 1
            AND l.is_active = 1
            """,
            (user_id,),
        ).fetchall()
        if rows:
            return {row["league_id"] for row in rows}

        rows = self.conn.execute(
            "SELECT id FROM leagues WHERE is_active = 1"
        ).fetchall()
        if rows:
            return {row["id"] for row in rows}

        rows = self.conn.execute(
            "SELECT id FROM leagues"
        ).fetchall()
        return {row["id"] for row in rows}

    def _obtenir_marches_autorises(self, user_id: int) -> set[str]:
        rows = self.conn.execute(
            """
            SELECT market
            FROM user_markets
            WHERE user_id = ?
            AND is_active = 1
            """,
            (user_id,),
        ).fetchall()
        if rows:
            return {row["market"] for row in rows}

        return set()
