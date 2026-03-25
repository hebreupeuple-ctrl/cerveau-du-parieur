"""
Modele Random Forest pour la prediction de marches de paris.
"""

import warnings
import numpy as np
from typing import Optional
from backend.core.logging import get_logger

warnings.filterwarnings(
    "ignore",
    message=r"`sklearn\.utils\.parallel\.delayed` should be used",
    category=UserWarning,
    module=r"sklearn\.utils\.parallel",
)

logger = get_logger(__name__)


class RandomForestPredictor:

    def __init__(self, marche: str):
        self.marche = marche
        self.modele = None
        self.est_entraine = False

    def entrainer(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> None:
        try:
            from sklearn.ensemble import RandomForestClassifier
            self.modele = RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
            self.modele.fit(X, y)
            self.est_entraine = True
            logger.info_ctx(
                "Random Forest entraine",
                context={"marche": self.marche, "n_samples": len(X)},
            )
        except Exception as e:
            logger.error_ctx(
                "Erreur entrainement Random Forest",
                context={"marche": self.marche, "erreur": str(e)},
            )

    def predire_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        if not self.est_entraine or self.modele is None:
            return None
        try:
            return self.modele.predict_proba(X)[:, 1]
        except Exception as e:
            logger.error_ctx(
                "Erreur prediction Random Forest",
                context={"erreur": str(e)},
            )
            return None

    def importances_features(self) -> Optional[np.ndarray]:
        if not self.est_entraine:
            return None
        return self.modele.feature_importances_
