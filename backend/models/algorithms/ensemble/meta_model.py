"""
Meta-modele de stacking avec calibration Platt scaling.
"""

import numpy as np
from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


class MetaModel:

    def __init__(self, marche: str):
        self.marche = marche
        # Poids fixes de repli si le stacking n'est pas entraîné
        self.poids = {
            "xgboost": 0.50,
            "random_forest": 0.30,
            "logistic_regression": 0.20,
        }
        self._stacking_model = None  # méta-apprenants entraîné sur prédictions OOF
        self.est_calibre = False
        self._calibrateur = None

    def entrainer_stacking(
        self,
        oof_xgb: np.ndarray,
        oof_rf: np.ndarray,
        oof_lr: np.ndarray,
        y: np.ndarray,
    ) -> None:
        """
        Entraîne le méta-apprenant de niveau 2 sur les prédictions OOF.
        Les poids sont appris par régression logistique sans biais,
        ce qui revient à apprendre les poids optimaux pour chaque modèle.
        """
        try:
            from sklearn.linear_model import LogisticRegression

            if len(np.unique(y)) < 2:
                logger.warning_ctx(
                    "Stacking ignoré : une seule classe dans y",
                    context={"marche": self.marche},
                )
                return

            X_meta = np.column_stack([oof_xgb, oof_rf, oof_lr])
            meta = LogisticRegression(
                C=1.0,
                solver="lbfgs",
                max_iter=500,
                fit_intercept=True,
                random_state=42,
            )
            meta.fit(X_meta, y)
            self._stacking_model = meta
            logger.info_ctx(
                "Stacking niveau 2 entraîné",
                context={
                    "marche": self.marche,
                    "coefs": [round(float(c), 4) for c in meta.coef_[0]],
                },
            )
        except Exception as e:
            logger.error_ctx(
                "Erreur entraînement stacking",
                context={"marche": self.marche, "erreur": str(e)},
            )

    def predire(
        self,
        pred_xgb: Optional[np.ndarray],
        pred_rf: Optional[np.ndarray],
        pred_lr: Optional[np.ndarray],
    ) -> Optional[np.ndarray]:
        actifs = [p for p in [pred_xgb, pred_rf, pred_lr] if p is not None]
        if not actifs:
            return None

        def _nettoyer(arr):
            """Remplace NaN par 0.5 (probabilité neutre) — évite propagation silencieuse."""
            if arr is None:
                return None
            cleaned = np.where(np.isnan(arr), 0.5, arr)
            return np.clip(cleaned, 0.0, 1.0)

        pred_xgb = _nettoyer(pred_xgb)
        pred_rf = _nettoyer(pred_rf)
        pred_lr = _nettoyer(pred_lr)

        # Stacking niveau 2 si disponible et toutes les prédictions présentes
        if (
            self._stacking_model is not None
            and pred_xgb is not None
            and pred_rf is not None
            and pred_lr is not None
        ):
            try:
                X_meta = np.column_stack([pred_xgb, pred_rf, pred_lr])
                result = self._stacking_model.predict_proba(X_meta)[:, 1]
                # Guard final contre NaN du stacking
                result = np.where(np.isnan(result), 0.5, result)
                return np.clip(result, 0.0, 1.0)
            except Exception:
                pass  # Repli sur moyenne pondérée

        # Repli : moyenne pondérée par les poids fixes
        predictions = []
        poids_actifs = []
        manquants = []
        for pred, key in zip(
            [pred_xgb, pred_rf, pred_lr],
            ["xgboost", "random_forest", "logistic_regression"],
        ):
            if pred is not None:
                predictions.append(pred)
                poids_actifs.append(self.poids[key])
            else:
                manquants.append(key)

        if manquants:
            logger.warning_ctx(
                "MetaModel : repli sur poids renormalisés (sous-modèle(s) manquant(s))",
                context={"marche": self.marche, "manquants": manquants},
            )

        poids_total = sum(poids_actifs)
        poids_normalises = [p / poids_total for p in poids_actifs]
        resultat = np.zeros_like(predictions[0])
        for pred, poids in zip(predictions, poids_normalises):
            resultat += pred * poids
        return np.clip(resultat, 0.0, 1.0)

    def calibrer(
        self,
        probas_brutes: np.ndarray,
        y_reel: np.ndarray,
    ) -> None:
        """
        Calibration Platt scaling : régression logistique sur les scores bruts.
        Corrige la sur/sous-confiance des probabilités combinées.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            if len(np.unique(y_reel)) < 2:
                logger.warning_ctx(
                    "Calibration ignorée : une seule classe dans y_reel",
                    context={"marche": self.marche},
                )
                self.est_calibre = False
                return

            calibrateur = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
            calibrateur.fit(probas_brutes.reshape(-1, 1), y_reel)
            self._calibrateur = calibrateur
            self.est_calibre = True

            probas_cal = calibrateur.predict_proba(probas_brutes.reshape(-1, 1))[:, 1]
            logger.info_ctx(
                "Calibration Platt terminée",
                context={
                    "marche": self.marche,
                    "mean_avant": round(float(probas_brutes.mean()), 4),
                    "mean_apres": round(float(probas_cal.mean()), 4),
                    "std_avant": round(float(probas_brutes.std()), 4),
                    "std_apres": round(float(probas_cal.std()), 4),
                },
            )
        except Exception as e:
            logger.error_ctx(
                "Erreur calibration Platt",
                context={"marche": self.marche, "erreur": str(e)},
            )
            self.est_calibre = False

    def appliquer_calibration(
        self,
        probas: np.ndarray,
    ) -> np.ndarray:
        if self.est_calibre and self._calibrateur is not None:
            try:
                calibrees = self._calibrateur.predict_proba(
                    probas.reshape(-1, 1)
                )[:, 1]
                return np.clip(calibrees, 0.01, 0.99)
            except Exception:
                pass
        return np.clip(probas, 0.01, 0.99)
