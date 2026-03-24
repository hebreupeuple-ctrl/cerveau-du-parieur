"""
Entraineur principal du modele ML.
Orchestre l'entrainement de tous les ensembles.
"""

import sqlite3
import numpy as np
import json
import os
import pickle
from typing import Optional
from datetime import datetime, timezone
from backend.core.logging import get_logger
from backend.core.config import settings
from backend.database.connection import obtenir_connexion
from backend.models.algorithms.ensemble.xgboost_model import XGBoostPredictor
from backend.models.algorithms.ensemble.random_forest import RandomForestPredictor
from backend.models.algorithms.ensemble.logistic_regression import LogisticRegressionPredictor
from backend.models.algorithms.ensemble.meta_model import MetaModel

logger = get_logger(__name__)

FEATURES_COLONNES = [
    "home_goals_scored_3m", "home_goals_scored_5m",
    "home_goals_scored_10m", "home_goals_scored_20m",
    "home_goals_conceded_3m", "home_goals_conceded_5m",
    "home_goals_conceded_10m", "home_goals_conceded_20m",
    "home_over25_rate_5m", "home_over25_rate_10m",
    "home_btts_rate_5m", "home_btts_rate_10m",
    "home_clean_sheet_rate_10m",
    "home_xg_generated_5m", "home_xg_conceded_5m",
    "home_xg_diff_5m", "home_ppm_5m", "home_ppm_10m",
    "home_win_streak", "home_momentum_score",
    "home_rest_days", "home_matches_last_14",
    "away_goals_scored_3m", "away_goals_scored_5m",
    "away_goals_scored_10m", "away_goals_scored_20m",
    "away_goals_conceded_3m", "away_goals_conceded_5m",
    "away_goals_conceded_10m", "away_goals_conceded_20m",
    "away_over25_rate_5m", "away_over25_rate_10m",
    "away_btts_rate_5m", "away_btts_rate_10m",
    "away_clean_sheet_rate_10m",
    "away_xg_generated_5m", "away_xg_conceded_5m",
    "away_xg_diff_5m", "away_ppm_5m", "away_ppm_10m",
    "away_win_streak", "away_momentum_score",
    "away_rest_days", "away_matches_last_14",
    "h2h_home_wins_5", "h2h_draws_5", "h2h_away_wins_5",
    "h2h_goals_avg_5", "h2h_btts_rate_5",
    "h2h_over25_rate_5", "h2h_dominance_score",
    "home_position_normalized", "home_points_gap_leader",
    "home_points_gap_relegation",
    "away_position_normalized", "away_points_gap_leader",
    "away_points_gap_relegation",
    "points_gap_between_teams",
    "league_goals_avg", "league_btts_rate",
    "league_over25_rate", "league_volatility",
    "match_importance_score", "game_week_normalized",
]

MARCHES = {
    "over25": "over25",
    "btts": "btts",
}


class ModelTrainer:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()
        self.modeles = {}

    def charger_donnees_entrainement(self) -> dict:
        """
        Charge les features et labels depuis la base de données.
        """
        logger.info("Chargement des données d'entraînement...")

        colonnes_sql = ", ".join(
            [f"mf.{c}" for c in FEATURES_COLONNES]
        )

        cursor = self.conn.execute(
            f"""
            SELECT
                {colonnes_sql},
                m.over25,
                m.btts,
                m.result_1x2,
                m.total_goals,
                m.match_timestamp
            FROM match_features mf
            JOIN matches m ON mf.match_id = m.id
            WHERE m.status = 'complete'
            AND m.home_goals IS NOT NULL
            AND m.over25 IS NOT NULL
            ORDER BY m.match_timestamp ASC
            """
        )
        rows = cursor.fetchall()

        if not rows:
            logger.warning("Aucune donnée d'entraînement trouvée")
            return {}

        X = []
        labels = {marche: [] for marche in MARCHES}

        for row in rows:
            features = []
            valide = True

            for col in FEATURES_COLONNES:
                val = row[col]
                if val is None:
                    val = 0.0
                features.append(float(val))

            X.append(features)
            labels["over25"].append(int(row["over25"] or 0))
            labels["btts"].append(int(row["btts"] or 0))

        X_array = np.array(X, dtype=np.float32)
        X_array = np.nan_to_num(X_array, nan=0.0)

        logger.info_ctx(
            "Données chargées",
            context={
                "n_matchs": len(X),
                "n_features": len(FEATURES_COLONNES),
            },
        )

        return {
            "X": X_array,
            "labels": {k: np.array(v) for k, v in labels.items()},
            "n_matchs": len(X),
        }

    def entrainer_marche(
        self,
        marche: str,
        X: np.ndarray,
        y: np.ndarray,
        ratio_train: float = 0.85,
    ) -> dict:
        """
        Entraine l'ensemble pour un marché donné.
        """
        logger.info_ctx(
            f"Entrainement marche {marche}",
            context={"n_samples": len(X), "positive_rate": float(y.mean())},
        )

        n_train = int(len(X) * ratio_train)
        X_train = X[:n_train]
        y_train = y[:n_train]
        X_test = X[n_train:]
        y_test = y[n_train:]

        xgb = XGBoostPredictor(marche)
        rf = RandomForestPredictor(marche)
        lr = LogisticRegressionPredictor(marche)
        meta = MetaModel(marche)

        xgb.entrainer(X_train, y_train)
        rf.entrainer(X_train, y_train)
        lr.entrainer(X_train, y_train)

        if len(X_test) > 0:
            pred_xgb = xgb.predire_proba(X_test)
            pred_rf = rf.predire_proba(X_test)
            pred_lr = lr.predire_proba(X_test)

            pred_combinee = meta.predire(pred_xgb, pred_rf, pred_lr)

            if pred_combinee is not None:
                meta.calibrer(pred_combinee, y_test)

            metriques = self._calculer_metriques(
                pred_combinee, y_test
            )
        else:
            metriques = {}

        self.modeles[marche] = {
            "xgboost": xgb,
            "random_forest": rf,
            "logistic_regression": lr,
            "meta": meta,
            "features": FEATURES_COLONNES,
        }

        logger.info_ctx(
            f"Marche {marche} entraine",
            context=metriques,
        )

        return metriques

    def entrainer_tous(self) -> dict:
        """
        Entraine l'ensemble complet pour tous les marchés.
        """
        donnees = self.charger_donnees_entrainement()
        if not donnees:
            return {}

        X = donnees["X"]
        resultats = {}

        for marche, col_label in MARCHES.items():
            y = donnees["labels"][marche]
            metriques = self.entrainer_marche(marche, X, y)
            resultats[marche] = metriques

        self._sauvegarder_modeles()
        return resultats

    def predire(
        self,
        features: dict,
    ) -> dict:
        """
        Génère les prédictions ML pour un match.
        """
        if not self.modeles:
            self._charger_modeles()

        X = np.array(
            [[features.get(col, 0.0) or 0.0 for col in FEATURES_COLONNES]],
            dtype=np.float32,
        )
        X = np.nan_to_num(X, nan=0.0)

        predictions = {}

        for marche, ensemble in self.modeles.items():
            pred_xgb = ensemble["xgboost"].predire_proba(X)
            pred_rf = ensemble["random_forest"].predire_proba(X)
            pred_lr = ensemble["logistic_regression"].predire_proba(X)

            pred_combinee = ensemble["meta"].predire(
                pred_xgb, pred_rf, pred_lr
            )

            if pred_combinee is not None:
                pred_calibree = ensemble["meta"].appliquer_calibration(
                    pred_combinee
                )
                predictions[f"ml_prob_{marche}"] = round(
                    float(pred_calibree[0]), 4
                )

        return predictions

    def _calculer_metriques(
        self,
        pred: Optional[np.ndarray],
        y_reel: np.ndarray,
    ) -> dict:
        if pred is None or len(y_reel) == 0:
            return {}

        try:
            from sklearn.metrics import (
                brier_score_loss,
                log_loss,
                roc_auc_score,
            )

            brier = brier_score_loss(y_reel, pred)
            logloss = log_loss(y_reel, pred)
            auc = roc_auc_score(y_reel, pred)

            pred_binaire = (pred >= 0.5).astype(int)
            accuracy = (pred_binaire == y_reel).mean()

            return {
                "brier_score": round(float(brier), 4),
                "log_loss": round(float(logloss), 4),
                "auc_roc": round(float(auc), 4),
                "accuracy": round(float(accuracy), 4),
                "n_test": len(y_reel),
            }
        except Exception as e:
            logger.error_ctx(
                "Erreur calcul métriques",
                context={"erreur": str(e)},
            )
            return {}

    def _sauvegarder_modeles(self) -> None:
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
        chemin = os.path.join(
            settings.MODELS_DIR, "ensemble_actuel.pkl"
        )
        with open(chemin, "wb") as f:
            pickle.dump(self.modeles, f)
        logger.info_ctx(
            "Modeles sauvegardés",
            context={"chemin": chemin},
        )

    def _charger_modeles(self) -> None:
        chemin = os.path.join(
            settings.MODELS_DIR, "ensemble_actuel.pkl"
        )
        if os.path.exists(chemin):
            with open(chemin, "rb") as f:
                self.modeles = pickle.load(f)
            logger.info("Modeles chargés depuis le disque")
        else:
            logger.warning("Aucun modele sauvegardé trouvé")
