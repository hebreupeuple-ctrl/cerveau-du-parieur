"""
Modele de Regression Logistique pour la calibration des probabilites.
"""

import numpy as np
from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


class LogisticRegressionPredictor:

    def __init__(self, marche: str):
        self.marche = marche
        self.modele = None
        self.scaler = None
        self.est_entraine = False

    def entrainer(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> None:
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler

            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.modele = LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
            self.modele.fit(X_scaled, y)
            self.est_entraine = True
            logger.info_ctx(
                "Regression Logistique entrainee",
                context={"marche": self.marche, "n_samples": len(X)},
            )
        except Exception as e:
            logger.error_ctx(
                "Erreur entrainement Regression Logistique",
                context={"marche": self.marche, "erreur": str(e)},
            )

    def predire_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        if not self.est_entraine or self.modele is None:
            return None
        try:
            X_scaled = self.scaler.transform(X)
            return self.modele.predict_proba(X_scaled)[:, 1]
        except Exception as e:
            logger.error_ctx(
                "Erreur prediction Regression Logistique",
                context={"erreur": str(e)},
            )
            return None
