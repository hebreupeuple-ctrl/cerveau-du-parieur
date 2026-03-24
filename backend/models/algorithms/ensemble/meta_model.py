"""
Meta-modele de stacking.
Combine les predictions sans calibration agressive.
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
        self.est_calibre = True
        logger.info_ctx(
            "Meta-modele prêt",
            context={
                "marche": self.marche,
                "std": round(float(probas_brutes.std()), 4),
                "mean": round(float(probas_brutes.mean()), 4),
            },
        )

    def appliquer_calibration(
        self,
        probas: np.ndarray,
    ) -> np.ndarray:
        return np.clip(probas, 0.05, 0.95)
