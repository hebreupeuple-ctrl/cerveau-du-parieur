"""
Modele XGBoost pour la prediction de marches de paris.
"""

import numpy as np
from typing import Optional
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class XGBoostPredictor:

    def __init__(self, marche: str):
        self.marche = marche
        self.modele = None
        self.est_entraine = False

    def entrainer(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None,
    ) -> None:
        try:
            import xgboost as xgb

            # Pondération des classes pour les labels déséquilibrés
            n_neg = int((y == 0).sum())
            n_pos = int((y == 1).sum())
            scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

            self.modele = xgb.XGBClassifier(
                n_estimators=500,
                max_depth=4,          # réduit de 5 → 4 pour limiter l'overfitting
                learning_rate=0.03,   # plus lent = plus stable
                subsample=0.75,
                colsample_bytree=0.65,  # réduit pour moins de features par arbre
                min_child_weight=10,  # exige plus d'échantillons par feuille
                gamma=0.1,            # pénalité sur les splits peu informatifs
                reg_alpha=0.05,       # L1 regularization
                reg_lambda=1.5,       # L2 regularization (renforcée)
                scale_pos_weight=scale_pos_weight,
                eval_metric="logloss",
                early_stopping_rounds=30,
                random_state=42,
                n_jobs=settings.MODEL_TRAIN_N_JOBS,
            )

            if X_val is not None and y_val is not None and len(X_val) >= 10:
                self.modele.fit(
                    X, y,
                    eval_set=[(X_val, y_val)],
                    verbose=False,
                )
            else:
                self.modele.set_params(early_stopping_rounds=None)
                self.modele.fit(X, y)
            self.est_entraine = True
            logger.info_ctx(
                "XGBoost entraine",
                context={"marche": self.marche, "n_samples": len(X)},
            )
        except Exception as e:
            logger.error_ctx(
                "Erreur entrainement XGBoost",
                context={"marche": self.marche, "erreur": str(e)},
            )

    def predire_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        if not self.est_entraine or self.modele is None:
            return None
        try:
            return self.modele.predict_proba(X)[:, 1]
        except Exception as e:
            logger.error_ctx(
                "Erreur prediction XGBoost",
                context={"erreur": str(e)},
            )
            return None

    def importances_features(self) -> Optional[np.ndarray]:
        if not self.est_entraine:
            return None
        return self.modele.feature_importances_
