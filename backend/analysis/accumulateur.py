"""
Generateur de pronostics.
Combine Dixon-Coles, ML, Value Betting et Kelly
pour produire les recommandations finales.
"""

import sqlite3
import time
import json
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion
from backend.models.algorithms.dixon_coles import DixonColesModel
from backend.models.trainer import ModelTrainer
from backend.analysis.value_betting import analyser_match
from backend.analysis.kelly import calculer_kelly_complet
from backend.features.pipeline import FeaturePipeline

logger = get_logger(__name__)


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

        max_time = match["match_timestamp"] - 3600

        features_row = self.conn.execute(
            "SELECT * FROM match_features WHERE match_id = ?",
            (match_id,),
        ).fetchone()

        if not features_row:
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

        probabilites_finales = self._fusionner_probabilites(
            pred_dc, pred_ml
        )

        if not probabilites_finales:
            return []

        matrice = pred_dc.get("score_matrix", {}) if pred_dc else {}

        cotes = self._obtenir_cotes(match_id)

        if not cotes:
            cotes = self._generer_cotes_reference(probabilites_finales)

        opportunites = analyser_match(
            probabilites_modele=probabilites_finales,
            cotes_disponibles=cotes,
            seuil_confiance=0.55,
        )

        pronostics = []
        for opp in opportunites:
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
    ) -> dict:
        """
        Fusionne les predictions DC et ML.
        DC = 60%, ML = 40% si ML disponible.
        DC = 100% si ML non disponible.
        """
        if not pred_dc:
            return {}

        proba_dc = {
            "prob_home_win": pred_dc.get("prob_home_win", 0.33),
            "prob_draw": pred_dc.get("prob_draw", 0.33),
            "prob_away_win": pred_dc.get("prob_away_win", 0.33),
            "prob_over15": pred_dc.get("prob_over15", 0.70),
            "prob_over25": pred_dc.get("prob_over25", 0.50),
            "prob_over35": pred_dc.get("prob_over35", 0.30),
            "prob_over45": pred_dc.get("prob_over45", 0.15),
            "prob_btts": pred_dc.get("prob_btts", 0.50),
            "prob_btts_no": pred_dc.get("prob_btts_no", 0.50),
        }

        if not pred_ml:
            return proba_dc

        poids_dc = 0.60
        poids_ml = 0.40

        result = {}
        for k, v_dc in proba_dc.items():
            cle_ml = f"ml_{k}"
            if cle_ml in pred_ml:
                v_ml = pred_ml[cle_ml]
                result[k] = round(
                    v_dc * poids_dc + v_ml * poids_ml, 4
                )
            else:
                result[k] = v_dc

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
        Applique une marge de 5% simulant un bookmaker moyen.
        """
        marge = 1.05

        cotes = {}

        if probabilites.get("prob_over25"):
            p = probabilites["prob_over25"]
            if p > 0.05:
                cotes["odds_over25"] = round(marge / p, 2)

        if probabilites.get("prob_btts"):
            p = probabilites["prob_btts"]
            if p > 0.05:
                cotes["odds_btts_yes"] = round(marge / p, 2)

        if probabilites.get("prob_over15"):
            p = probabilites["prob_over15"]
            if p > 0.05:
                cotes["odds_over15"] = round(marge / p, 2)

        if probabilites.get("prob_home_win"):
            p = probabilites["prob_home_win"]
            if p > 0.05:
                cotes["odds_home"] = round(marge / p, 2)

        if probabilites.get("prob_draw"):
            p = probabilites["prob_draw"]
            if p > 0.05:
                cotes["odds_draw"] = round(marge / p, 2)

        if probabilites.get("prob_away_win"):
            p = probabilites["prob_away_win"]
            if p > 0.05:
                cotes["odds_away"] = round(marge / p, 2)

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
        dans_48h = maintenant + (48 * 3600)

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
            ORDER BY m.match_timestamp ASC
            """,
            (maintenant, dans_48h),
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
            )
            tous_pronostics.extend(pronostics)

        tous_pronostics.sort(
            key=lambda x: x["ev"],
            reverse=True,
        )

        return tous_pronostics[:max_pronostics]
