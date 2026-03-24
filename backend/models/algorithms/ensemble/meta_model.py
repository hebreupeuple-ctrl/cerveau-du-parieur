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
        self.poids = {
            "xgboost": 0.50,
            "random_forest": 0.30,
            "logistic_regression": 0.20,
        }
        self.est_calibre = False
        self._calibrateur = None

    def predire(
        self,
        pred_xgb: Optional[np.ndarray],
        pred_rf: Optional[np.ndarray],
        pred_lr: Optional[np.ndarray],
    ) -> Optional[np.ndarray]:
        predictions = []
        poids_actifs = []

        if pred_xgb is not None:
            predictions.append(pred_xgb)
            poids_actifs.append(self.poids["xgboost"])
        if pred_rf is not None:
            predictions.append(pred_rf)
            poids_actifs.append(self.poids["random_forest"])
        if pred_lr is not None:
            predictions.append(pred_lr)
            poids_actifs.append(self.poids["logistic_regression"])

        if not predictions:
            return None

        poids_total = sum(poids_actifs)
        poids_normalises = [p / poids_total for p in poids_actifs]

        resultat = np.zeros_like(predictions[0])
        for pred, poids in zip(predictions, poids_normalises):
            resultat += pred * poids

        return resultat

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
                return np.clip(calibrees, 0.02, 0.98)
            except Exception:
                pass
        return np.clip(probas, 0.02, 0.98)
