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

# Colonnes lues depuis la base de données
FEATURES_COLONNES = [
    # Forme récente (buts, taux, points)
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
    # H2H
    "h2h_home_wins_5", "h2h_draws_5", "h2h_away_wins_5",
    "h2h_goals_avg_5", "h2h_btts_rate_5",
    "h2h_over25_rate_5", "h2h_dominance_score",
    # Classement
    "home_position_normalized", "home_points_gap_leader",
    "home_points_gap_relegation",
    "away_position_normalized", "away_points_gap_leader",
    "away_points_gap_relegation",
    "points_gap_between_teams",
    # Ligue & contexte
    "league_goals_avg", "league_btts_rate",
    "league_over25_rate", "league_volatility",
    "match_importance_score", "game_week_normalized",
    # Tirs, corners, possession (physique — absents pour 83% des matchs)
    # Le flag has_physical_data (ci-dessous) indique leur disponibilité réelle
    "home_shots_avg_5m", "home_shots_on_target_avg_5m",
    "home_corners_avg_5m", "home_possession_avg_5m",
    "home_conversion_rate_5m", "home_shot_efficiency_5m",
    "home_goals_ht_avg_5m", "home_over15_ht_rate_5m",
    "home_ht_win_rate_5m", "home_ht_draw_rate_5m",
    "home_fatigue_score",
    "away_shots_avg_5m", "away_shots_on_target_avg_5m",
    "away_corners_avg_5m", "away_possession_avg_5m",
    "away_conversion_rate_5m", "away_shot_efficiency_5m",
    "away_goals_ht_avg_5m", "away_over15_ht_rate_5m",
    "away_ht_win_rate_5m", "away_ht_draw_rate_5m",
    "away_fatigue_score",
]

# Feature virtuelle calculée (pas une colonne DB) : ajoutée après la boucle FEATURES_COLONNES
# Vaut 1 quand les données physiques (tirs/corners/possession) sont disponibles, 0 sinon.
# Permet au modèle de pondérer correctement les features physiques imputées.
FEATURE_VIRTUELLE_PHYSIQUE = "has_physical_data"

# Features d'interaction (dérivées de combinaisons de features existantes).
# Ces features capturent directement la dynamique match-niveau (attaque A × défense B)
# qui est le signal le plus prédictif pour les marchés over/btts.
FEATURES_INTERACTION = [
    # xG total attendu pour le match (meilleur prédicteur direct d'over 2.5)
    "match_xg_total",
    # Proxy buts attendus domicile : moyenne de l'attaque home et de la défense away
    "home_expected_goals_proxy",
    # Proxy buts attendus extérieur : moyenne de l'attaque away et de la défense home
    "away_expected_goals_proxy",
    # Total attendu via buts (indépendant du xG, plus robuste pour les ligues sans xG)
    "match_goals_proxy",
    # Probabilité over25 combinée des deux équipes (produit des taux individuels)
    "over25_probability_product",
    # Probabilité BTTS combinée (produit des taux de scoring des deux équipes)
    "btts_probability_product",
    # ── Normalisation par la moyenne de ligue ──────────────────────────────
    # Ces features mesurent la PERFORMANCE RELATIVE de chaque équipe vs sa ligue.
    # Sans normalisation, "2 buts/match" en PL ≠ "2 buts/match" en D3 → bruit pur.
    # Performance offensive home vs moyenne de ligue (>1 = meilleure que moyenne)
    "home_attack_vs_league",
    # Performance défensive away vs moyenne de ligue (<1 = meilleure que moyenne)
    "away_defense_vs_league",
    # Performance offensive away vs moyenne de ligue
    "away_attack_vs_league",
    # Performance défensive home vs moyenne de ligue
    "home_defense_vs_league",
    # Taux over25 home vs taux de ligue (positif = équipe sur-performe la ligue)
    "home_over25_vs_league",
    # Taux over25 away vs taux de ligue
    "away_over25_vs_league",
]

# Noms complets des features utilisées par le modèle (DB + virtuelles + interactions)
FEATURES_NOMS = FEATURES_COLONNES + [FEATURE_VIRTUELLE_PHYSIQUE] + FEATURES_INTERACTION

MARCHES = {
    "over15":      "over15",
    "over25":      "over25",
    "btts":        "btts",
    "home_win":    "home_win",
    "draw":        "draw",
    "away_win":    "away_win",
    "ht_home_win": "ht_home_win",  # 1x2 mi-temps : victoire domicile à la pause
    "ht_draw":     "ht_draw",      # 1x2 mi-temps : nul à la pause
    "ht_away_win": "ht_away_win",  # 1x2 mi-temps : victoire extérieur à la pause
}


def _calculer_features_interaction(features_dict: dict) -> list:
    """
    Calcule les features d'interaction à partir du dictionnaire de features brutes.
    Ces features capturent directement la dynamique match-niveau.
    Retourne une liste de valeurs dans l'ordre de FEATURES_INTERACTION.

    Les features xG retournent np.nan quand la donnée est absente (≠ 0.0)
    pour que l'imputation par médiane s'applique correctement à l'entraînement
    et à l'inférence — évite de confondre "pas de données xG" avec "0 xG".
    """
    def safe(key: str, default: float = 0.0) -> float:
        v = features_dict.get(key)
        return float(v) if v is not None else default

    def safe_xg(key: str) -> float:
        """Retourne np.nan si absent : distingue donnée manquante de vrai zéro."""
        v = features_dict.get(key)
        return float(v) if v is not None else np.nan

    home_xg_gen  = safe_xg("home_xg_generated_5m")
    away_xg_gen  = safe_xg("away_xg_generated_5m")
    home_goals_s = safe("home_goals_scored_5m")
    away_goals_s = safe("away_goals_scored_5m")
    home_goals_c = safe("home_goals_conceded_5m")
    away_goals_c = safe("away_goals_conceded_5m")
    home_o25     = safe("home_over25_rate_5m")
    away_o25     = safe("away_over25_rate_5m")
    home_btts    = safe("home_btts_rate_5m")
    away_btts    = safe("away_btts_rate_5m")
    league_avg   = safe("league_goals_avg", default=2.5)
    league_o25   = safe("league_over25_rate", default=0.489)

    # xG total : NaN si l'un des deux manque (sera imputé par médiane)
    if np.isnan(home_xg_gen) or np.isnan(away_xg_gen):
        match_xg_total = np.nan
    else:
        match_xg_total = round(home_xg_gen + away_xg_gen, 3)

    # Proxy buts attendus home : moyenne entre "ce que home marque" et "ce qu'away concède"
    home_expected = round((home_goals_s + away_goals_c) / 2, 3)

    # Proxy buts attendus away : moyenne entre "ce qu'away marque" et "ce que home concède"
    away_expected = round((away_goals_s + home_goals_c) / 2, 3)

    # Total buts attendus via forme
    match_goals_proxy = round(home_expected + away_expected, 3)

    # Produit des taux over25 des deux équipes
    over25_product = round(home_o25 * away_o25, 4)

    # Produit des taux btts
    btts_product = round(home_btts * away_btts, 4)

    # ── Normalisation par la ligue ────────────────────────────────────────
    # Diviser par la moyenne de ligue (demi-buts par équipe ≈ league_avg/2)
    # Garantit que "2 buts/match en PL" et "2 buts/match en D3" signifient la même chose.
    half_league = league_avg / 2 if league_avg > 0 else 1.25

    home_attack_vs_league  = round(home_goals_s / half_league, 3) if half_league > 0 else 1.0
    away_defense_vs_league = round(away_goals_c / half_league, 3) if half_league > 0 else 1.0
    away_attack_vs_league  = round(away_goals_s / half_league, 3) if half_league > 0 else 1.0
    home_defense_vs_league = round(home_goals_c / half_league, 3) if half_league > 0 else 1.0

    home_o25_vs_league = round(home_o25 - league_o25, 3)
    away_o25_vs_league = round(away_o25 - league_o25, 3)

    return [
        match_xg_total,
        home_expected,
        away_expected,
        match_goals_proxy,
        over25_product,
        btts_product,
        home_attack_vs_league,
        away_defense_vs_league,
        away_attack_vs_league,
        home_defense_vs_league,
        home_o25_vs_league,
        away_o25_vs_league,
    ]


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
                m.over15,
                m.over25,
                m.btts,
                m.home_goals_ht,
                m.away_goals_ht,
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

            for col in FEATURES_COLONNES:
                val = row[col]
                features.append(float(val) if val is not None else np.nan)

            # Feature virtuelle : 1 si données physiques disponibles, 0 sinon.
            # Calculée AVANT imputation pour capturer la vraie disponibilité.
            has_physical = 1.0 if row["home_shots_avg_5m"] is not None else 0.0
            features.append(has_physical)

            # Features d'interaction (calculées depuis les valeurs brutes pré-imputation)
            row_dict = {col: row[col] for col in FEATURES_COLONNES}
            features.extend(_calculer_features_interaction(row_dict))

            X.append(features)
            labels["over15"].append(int(row["over15"] or 0))
            labels["over25"].append(int(row["over25"] or 0))
            labels["btts"].append(int(row["btts"] or 0))
            # 1x2 FT
            r1x2 = row["result_1x2"]
            labels["home_win"].append(1 if r1x2 == "1" else 0)
            labels["draw"].append(1 if r1x2 == "X" else 0)
            labels["away_win"].append(1 if r1x2 == "2" else 0)
            # 1x2 mi-temps : np.nan quand données absentes (évite les faux 0)
            hg_ht = row["home_goals_ht"]
            ag_ht = row["away_goals_ht"]
            if hg_ht is not None and ag_ht is not None:
                labels["ht_home_win"].append(float(1 if hg_ht > ag_ht else 0))
                labels["ht_draw"].append(float(1 if hg_ht == ag_ht else 0))
                labels["ht_away_win"].append(float(1 if ag_ht > hg_ht else 0))
            else:
                labels["ht_home_win"].append(np.nan)
                labels["ht_draw"].append(np.nan)
                labels["ht_away_win"].append(np.nan)

        X_array = np.array(X, dtype=np.float32)

        # Imputation par médiane par feature (évite le biais du 0 uniforme)
        self.feature_medians = np.nanmedian(X_array, axis=0)
        # Fallback à 0.0 si toute la colonne est NaN
        self.feature_medians = np.where(
            np.isnan(self.feature_medians), 0.0, self.feature_medians
        )
        for i in range(X_array.shape[1]):
            nan_mask = np.isnan(X_array[:, i])
            if nan_mask.any():
                X_array[nan_mask, i] = self.feature_medians[i]

        logger.info_ctx(
            "Données chargées",
            context={
                "n_matchs": len(X),
                "n_features": len(FEATURES_NOMS),
            },
        )

        labels_arrays = {marche: np.array(vals, dtype=np.float32) for marche, vals in labels.items()}

        return {
            "X": X_array,
            "labels": labels_arrays,
            "n_matchs": len(X),
            "training_data_start": self._timestamp_vers_iso(rows[0]["match_timestamp"]),
            "training_data_end": self._timestamp_vers_iso(rows[-1]["match_timestamp"]),
        }

    def entrainer_marche(
        self,
        marche: str,
        X: np.ndarray,
        y: np.ndarray,
        ratio_train: float = 0.75,
        ratio_cal: float = 0.10,
    ) -> dict:
        """
        Entraine l'ensemble pour un marché donné.
        Split 3-way : 75% train / 10% calibration / 15% test.
        - X_train  : entraînement des modèles de base + stacking OOF
        - X_cal    : calibration Platt (données indépendantes du test)
        - X_test   : évaluation finale (données jamais vues par le modèle)
        """
        logger.info_ctx(
            f"Entrainement marche {marche}",
            context={"n_samples": len(X), "positive_rate": float(y.mean())},
        )

        n_train = int(len(X) * ratio_train)
        n_cal   = int(len(X) * ratio_cal)
        X_train = X[:n_train]
        y_train = y[:n_train]
        X_cal   = X[n_train:n_train + n_cal]
        y_cal   = y[n_train:n_train + n_cal]
        X_test  = X[n_train + n_cal:]
        y_test  = y[n_train + n_cal:]

        xgb = XGBoostPredictor(marche)
        rf = RandomForestPredictor(marche)
        lr = LogisticRegressionPredictor(marche)
        meta = MetaModel(marche)

        # ── Stacking OOF : génère des prédictions hors-échantillon
        #    sur le set d'entraînement pour apprendre les poids du méta-apprenant
        if len(X_train) >= 100:
            self._entrainer_stacking_oof(meta, marche, X_train, y_train)

        # Entraînement final sur l'intégralité du set d'entraînement
        # XGBoost : early stopping sur X_cal (séparé du test) pour nb optimal d'arbres
        xgb.entrainer(X_train, y_train, X_val=X_cal, y_val=y_cal)
        rf.entrainer(X_train, y_train)
        lr.entrainer(X_train, y_train)

        # Calibration Platt sur X_cal (données indépendantes de X_test)
        if len(X_cal) >= 20:
            pred_xgb_cal = xgb.predire_proba(X_cal)
            pred_rf_cal  = rf.predire_proba(X_cal)
            pred_lr_cal  = lr.predire_proba(X_cal)
            pred_cal     = meta.predire(pred_xgb_cal, pred_rf_cal, pred_lr_cal)
            if pred_cal is not None:
                meta.calibrer(pred_cal, y_cal)

        # Évaluation finale sur X_test (jamais vu — métriques non biaisées)
        if len(X_test) > 0:
            pred_xgb = xgb.predire_proba(X_test)
            pred_rf  = rf.predire_proba(X_test)
            pred_lr  = lr.predire_proba(X_test)

            pred_combinee = meta.predire(pred_xgb, pred_rf, pred_lr)
            # Appliquer la calibration pour avoir des métriques représentatives du prod
            if pred_combinee is not None and meta.est_calibre:
                pred_combinee = meta.appliquer_calibration(pred_combinee)

            metriques = self._calculer_metriques(pred_combinee, y_test)
        else:
            metriques = {}

        self.modeles[marche] = {
            "xgboost": xgb,
            "random_forest": rf,
            "logistic_regression": lr,
            "meta": meta,
            "features": FEATURES_NOMS,
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
        N_MIN = 500  # Exemples minimum pour entraîner un marché

        for marche in MARCHES:
            y_all = donnees["labels"][marche]

            # Filtrer les exemples valides (nan = label manquant, ex. HT sans données)
            valid_mask = ~np.isnan(y_all)
            n_valid = int(valid_mask.sum())
            n_pos = int(y_all[valid_mask].sum()) if n_valid > 0 else 0

            if n_valid < N_MIN:
                logger.warning_ctx(
                    f"Marche {marche} ignoree : données insuffisantes",
                    context={"n_valid": n_valid, "n_min": N_MIN},
                )
                resultats[marche] = {"skipped": True, "n_valid": n_valid}
                continue

            X_marche = X[valid_mask]
            y_marche = y_all[valid_mask].astype(np.int32)

            metriques = self.entrainer_marche(marche, X_marche, y_marche)
            resultats[marche] = metriques

        chemin = self._sauvegarder_modeles()
        self._enregistrer_version_modele(
            n_matchs=donnees["n_matchs"],
            resultats=resultats,
            training_data_start=donnees["training_data_start"],
            training_data_end=donnees["training_data_end"],
            artifact_path=chemin,
        )
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

        raw = [
            float(features[col]) if features.get(col) is not None else np.nan
            for col in FEATURES_COLONNES
        ]
        # Feature virtuelle : calculée AVANT imputation (même logique qu'à l'entraînement)
        has_physical = 1.0 if features.get("home_shots_avg_5m") is not None else 0.0
        raw.append(has_physical)

        # Features d'interaction : calculées depuis les valeurs brutes pré-imputation
        raw.extend(_calculer_features_interaction(features))

        X = np.array([raw], dtype=np.float32)

        # Imputation par médianes apprises à l'entraînement
        medians = getattr(self, "feature_medians", None)
        for i in range(X.shape[1]):
            if np.isnan(X[0, i]):
                X[0, i] = float(medians[i]) if medians is not None else 0.0

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

    def _entrainer_stacking_oof(
        self,
        meta: MetaModel,
        marche: str,
        X_train: np.ndarray,
        y_train: np.ndarray,
        n_splits: int = 5,
    ) -> None:
        """
        Génère des prédictions OOF (out-of-fold) par time-series split
        et entraîne le méta-apprenant de stacking.
        """
        try:
            from sklearn.model_selection import TimeSeriesSplit

            tscv = TimeSeriesSplit(n_splits=n_splits)
            oof_xgb = np.zeros(len(X_train))
            oof_rf = np.zeros(len(X_train))
            oof_lr = np.zeros(len(X_train))

            for train_idx, val_idx in tscv.split(X_train):
                if len(train_idx) < 20 or len(val_idx) < 5:
                    continue
                X_f = X_train[train_idx]
                y_f = y_train[train_idx]
                X_v = X_train[val_idx]

                xgb_f = XGBoostPredictor(marche)
                rf_f = RandomForestPredictor(marche)
                lr_f = LogisticRegressionPredictor(marche)

                xgb_f.entrainer(X_f, y_f)
                rf_f.entrainer(X_f, y_f)
                lr_f.entrainer(X_f, y_f)

                p = xgb_f.predire_proba(X_v)
                if p is not None:
                    oof_xgb[val_idx] = p
                p = rf_f.predire_proba(X_v)
                if p is not None:
                    oof_rf[val_idx] = p
                p = lr_f.predire_proba(X_v)
                if p is not None:
                    oof_lr[val_idx] = p

            meta.entrainer_stacking(oof_xgb, oof_rf, oof_lr, y_train)

        except Exception as e:
            logger.error_ctx(
                "Erreur génération OOF stacking",
                context={"marche": marche, "erreur": str(e)},
            )

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

    def _sauvegarder_modeles(self) -> str:
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
        chemin = os.path.join(
            settings.MODELS_DIR, "ensemble_actuel.pkl"
        )
        payload = {
            "modeles": self.modeles,
            "feature_medians": getattr(self, "feature_medians", None),
        }
        with open(chemin, "wb") as f:
            pickle.dump(payload, f)
        logger.info_ctx(
            "Modeles sauvegardés",
            context={"chemin": chemin},
        )
        return chemin

    def _charger_modeles(self) -> None:
        chemin = os.path.join(
            settings.MODELS_DIR, "ensemble_actuel.pkl"
        )
        if os.path.exists(chemin):
            import warnings
            from sklearn.exceptions import InconsistentVersionWarning
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", InconsistentVersionWarning)
                with open(chemin, "rb") as f:
                    payload = pickle.load(f)

            if any(issubclass(w.category, InconsistentVersionWarning) for w in caught):
                logger.warning_ctx(
                    "Modèle sklearn obsolète (version incompatible) — réentraînement forcé",
                    context={"chemin": chemin},
                )
                try:
                    os.remove(chemin)
                except OSError:
                    pass
                return

            # Compatibilité avec l'ancien format (dict de modèles directement)
            if isinstance(payload, dict) and "modeles" in payload:
                self.modeles = payload["modeles"]
                self.feature_medians = payload.get("feature_medians")
            else:
                self.modeles = payload
                self.feature_medians = None

            # Vérifier que le modèle correspond au nombre de features attendu
            n_attendu = len(FEATURES_NOMS)
            n_modele = None
            for ensemble in self.modeles.values():
                feats = ensemble.get("features")
                if feats is not None:
                    n_modele = len(feats)
                    break
            if n_modele is not None and n_modele != n_attendu:
                logger.warning_ctx(
                    "Modèle obsolète détecté — réentraînement automatique",
                    context={"n_modele": n_modele, "n_attendu": n_attendu},
                )
                self.modeles = {}
                self.feature_medians = None
                try:
                    os.remove(chemin)
                except OSError:
                    pass
            else:
                logger.info("Modeles chargés depuis le disque")
        else:
            logger.warning("Aucun modele sauvegardé trouvé")

    def _enregistrer_version_modele(
        self,
        n_matchs: int,
        resultats: dict,
        training_data_start: str,
        training_data_end: str,
        artifact_path: str,
    ) -> None:
        version = datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M%S")
        over25 = resultats.get("over25", {})
        btts = resultats.get("btts", {})

        nouveau_brier_over25 = over25.get("brier_score")
        nouveau_brier_btts = btts.get("brier_score")

        # Validation : ne pas activer si le nouveau modèle est dégradé
        actif_precedent = self.conn.execute(
            """
            SELECT brier_score_over25, brier_score_btts, version
            FROM model_versions
            WHERE is_active = 1
            LIMIT 1
            """
        ).fetchone()

        activer = True
        if (
            actif_precedent
            and nouveau_brier_over25 is not None
            and nouveau_brier_btts is not None
            and actif_precedent["brier_score_over25"] is not None
            and actif_precedent["brier_score_btts"] is not None
        ):
            # Brier score : plus bas = meilleur. Tolérance 5%.
            seuil_degradation = 1.05
            degradation_over25 = (
                nouveau_brier_over25
                > actif_precedent["brier_score_over25"] * seuil_degradation
            )
            degradation_btts = (
                nouveau_brier_btts
                > actif_precedent["brier_score_btts"] * seuil_degradation
            )
            if degradation_over25 or degradation_btts:
                activer = False
                logger.warning_ctx(
                    "Nouveau modele plus faible que le precedent — NON activé",
                    context={
                        "version_precedente": actif_precedent["version"],
                        "brier_over25_ancien": actif_precedent["brier_score_over25"],
                        "brier_over25_nouveau": nouveau_brier_over25,
                        "brier_btts_ancien": actif_precedent["brier_score_btts"],
                        "brier_btts_nouveau": nouveau_brier_btts,
                    },
                )

        if activer:
            self.conn.execute(
                "UPDATE model_versions SET is_active = 0 WHERE is_active = 1"
            )

        self.conn.execute(
            """
            INSERT INTO model_versions (
                version, trained_at,
                training_data_start, training_data_end,
                total_matches_trained,
                brier_score_over25, brier_score_btts,
                log_loss_over25, log_loss_btts,
                auc_roc_over25, auc_roc_btts,
                selected_features_json, artifact_path, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                datetime.now(timezone.utc).isoformat(),
                training_data_start,
                training_data_end,
                n_matchs,
                nouveau_brier_over25,
                nouveau_brier_btts,
                over25.get("log_loss"),
                btts.get("log_loss"),
                over25.get("auc_roc"),
                btts.get("auc_roc"),
                json.dumps(FEATURES_NOMS, ensure_ascii=False),
                artifact_path,
                1 if activer else 0,
            ),
        )
        self.conn.commit()

        logger.info_ctx(
            "Version modele enregistree",
            context={"version": version, "active": activer},
        )

    def recalibrer_platt(self) -> dict:
        """
        Recalibration Platt légère : re-ajuste uniquement les calibrateurs
        sur des matchs récents (depuis la fin des données d'entraînement),
        sans réentraîner les modèles de base.

        Utile pour corriger le drift de calibration entre deux réentraînements
        complets, avec un coût CPU bien inférieur (pas de XGBoost/RF/OOF).
        """
        if not self.modeles:
            self._charger_modeles()

        if not self.modeles:
            return {"skipped": True, "reason": "aucun_modele_charge"}

        # Récupérer la date de fin des données d'entraînement du modèle actif
        row = self.conn.execute(
            """
            SELECT training_data_end
            FROM model_versions
            WHERE is_active = 1
            ORDER BY trained_at DESC
            LIMIT 1
            """
        ).fetchone()

        if not row or not row["training_data_end"]:
            return {"skipped": True, "reason": "version_modele_introuvable"}

        training_end_iso = row["training_data_end"]
        # Convertir en timestamp Unix
        from datetime import datetime as _dt
        training_end_ts = int(
            _dt.fromisoformat(training_end_iso.replace("Z", "+00:00")).timestamp()
        )

        colonnes_sql = ", ".join([f"mf.{c}" for c in FEATURES_COLONNES])
        cursor = self.conn.execute(
            f"""
            SELECT
                {colonnes_sql},
                m.over15, m.over25, m.btts,
                m.home_goals_ht, m.away_goals_ht,
                m.result_1x2, m.total_goals, m.match_timestamp
            FROM match_features mf
            JOIN matches m ON mf.match_id = m.id
            WHERE m.status = 'complete'
            AND m.home_goals IS NOT NULL
            AND m.over25 IS NOT NULL
            AND m.match_timestamp > ?
            ORDER BY m.match_timestamp ASC
            """,
            (training_end_ts,),
        )
        rows = cursor.fetchall()

        N_MIN_CAL = 200
        if len(rows) < N_MIN_CAL:
            return {
                "skipped": True,
                "reason": f"donnees_insuffisantes ({len(rows)} < {N_MIN_CAL})",
            }

        X = []
        labels = {marche: [] for marche in MARCHES}

        for row in rows:
            raw = [
                float(row[col]) if row[col] is not None else np.nan
                for col in FEATURES_COLONNES
            ]
            has_physical = 1.0 if row["home_shots_avg_5m"] is not None else 0.0
            raw.append(has_physical)

            row_dict = {col: row[col] for col in FEATURES_COLONNES}
            raw.extend(_calculer_features_interaction(row_dict))
            X.append(raw)

            hg = row["home_goals"] if hasattr(row, "__getitem__") else None
            hg_ht = row["home_goals_ht"]
            ag_ht = row["away_goals_ht"]
            r = row["result_1x2"]
            tg = row["total_goals"] or 0
            o15 = row["over15"]
            o25 = row["over25"]
            btts = row["btts"]

            labels["over25"].append(float(o25) if o25 is not None else np.nan)
            labels["btts"].append(float(btts) if btts is not None else np.nan)
            labels["over15"].append(float(o15) if o15 is not None else np.nan)
            labels["over45"].append(float(1 if tg > 4 else 0))
            labels["home_win"].append(float(1 if r == "home" else 0) if r else np.nan)
            labels["draw"].append(float(1 if r == "draw" else 0) if r else np.nan)
            labels["away_win"].append(float(1 if r == "away" else 0) if r else np.nan)

            if hg_ht is not None and ag_ht is not None:
                labels["ht_home_win"].append(float(1 if hg_ht > ag_ht else 0))
                labels["ht_draw"].append(float(1 if hg_ht == ag_ht else 0))
                labels["ht_away_win"].append(float(1 if ag_ht > hg_ht else 0))
            else:
                labels["ht_home_win"].append(np.nan)
                labels["ht_draw"].append(np.nan)
                labels["ht_away_win"].append(np.nan)

        X_all = np.array(X, dtype=np.float32)
        medians = getattr(self, "feature_medians", None)
        for i in range(X_all.shape[1]):
            col_nan = np.isnan(X_all[:, i])
            if col_nan.any():
                fill = float(medians[i]) if medians is not None else 0.0
                X_all[col_nan, i] = fill

        resultats = {}
        for marche, ensemble in self.modeles.items():
            y_all = np.array(labels.get(marche, []), dtype=np.float32)
            valid_mask = ~np.isnan(y_all)
            n_valid = int(valid_mask.sum())
            if n_valid < 50:
                resultats[marche] = {"skipped": True, "n_valid": n_valid}
                continue

            X_cal = X_all[valid_mask]
            y_cal = y_all[valid_mask].astype(np.int32)

            pred_xgb = ensemble["xgboost"].predire_proba(X_cal)
            pred_rf  = ensemble["random_forest"].predire_proba(X_cal)
            pred_lr  = ensemble["logistic_regression"].predire_proba(X_cal)
            pred_brute = ensemble["meta"].predire(pred_xgb, pred_rf, pred_lr)

            if pred_brute is not None and len(pred_brute) >= 20:
                ensemble["meta"].calibrer(pred_brute, y_cal)
                resultats[marche] = {"recalibre": True, "n_cal": n_valid}
            else:
                resultats[marche] = {"skipped": True, "reason": "prediction_echec"}

        self._sauvegarder_modeles()
        logger.info_ctx(
            "Recalibration Platt terminée",
            context={"resultats": resultats},
        )
        return {"recalibration": resultats, "n_matchs_cal": len(rows)}

    def _timestamp_vers_iso(self, timestamp: int) -> str:
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()
