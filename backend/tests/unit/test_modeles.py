"""
Tests unitaires pour les modèles de prédiction.
Couvre : Dixon-Coles, MetaModel (stacking/calibration/fallback), Accumulateur (fusion DC/ML).
"""

import numpy as np
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Dixon-Coles
# ─────────────────────────────────────────────────────────────────────────────

class TestCorrectionRho:
    """Tests pour la correction rho de Dixon-Coles."""

    def test_score_0_0(self):
        from backend.models.algorithms.dixon_coles import correction_rho
        rho = -0.13
        lam, mu = 1.5, 1.2
        result = correction_rho(0, 0, lam, mu, rho)
        assert result == pytest.approx(1 - lam * mu * rho, abs=1e-9)

    def test_score_1_0(self):
        from backend.models.algorithms.dixon_coles import correction_rho
        rho = -0.13
        lam, mu = 1.5, 1.2
        result = correction_rho(1, 0, lam, mu, rho)
        assert result == pytest.approx(1 + mu * rho, abs=1e-9)

    def test_score_0_1(self):
        from backend.models.algorithms.dixon_coles import correction_rho
        rho = -0.13
        lam, mu = 1.5, 1.2
        result = correction_rho(0, 1, lam, mu, rho)
        assert result == pytest.approx(1 + lam * rho, abs=1e-9)

    def test_score_1_1(self):
        from backend.models.algorithms.dixon_coles import correction_rho
        rho = -0.13
        result = correction_rho(1, 1, 1.5, 1.2, rho)
        assert result == pytest.approx(1 - rho, abs=1e-9)

    def test_score_haut_pas_de_correction(self):
        from backend.models.algorithms.dixon_coles import correction_rho
        # Pour tous les autres scores, correction = 1.0
        for (h, a) in [(2, 0), (0, 2), (2, 2), (3, 1), (0, 3)]:
            assert correction_rho(h, a, 1.5, 1.2, -0.13) == 1.0


class TestPoisson:
    def test_proba_0_lambda_1(self):
        from backend.models.algorithms.dixon_coles import poisson_prob
        assert poisson_prob(0, 1.0) == pytest.approx(np.exp(-1.0), abs=1e-9)

    def test_proba_lambda_zero(self):
        from backend.models.algorithms.dixon_coles import poisson_prob
        assert poisson_prob(0, 0.0) == 1.0
        assert poisson_prob(1, 0.0) == 0.0

    def test_proba_positive(self):
        from backend.models.algorithms.dixon_coles import poisson_prob
        for k in range(5):
            assert poisson_prob(k, 1.5) >= 0.0


class TestMatriceScores:
    def test_somme_egale_1(self):
        from backend.models.algorithms.dixon_coles import calculer_matrice_scores
        matrice = calculer_matrice_scores(1.5, 1.2)
        total = sum(matrice.values())
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_toutes_proba_positives(self):
        from backend.models.algorithms.dixon_coles import calculer_matrice_scores
        matrice = calculer_matrice_scores(1.5, 1.2)
        for v in matrice.values():
            assert v >= 0.0

    def test_cle_format(self):
        from backend.models.algorithms.dixon_coles import calculer_matrice_scores
        matrice = calculer_matrice_scores(1.5, 1.2)
        assert "0-0" in matrice
        assert "1-0" in matrice
        assert "2-1" in matrice

    def test_lambda_eleve_plus_de_buts(self):
        """Une lambda élevée doit augmenter la probabilité de scores élevés à domicile."""
        from backend.models.algorithms.dixon_coles import calculer_matrice_scores
        m_bas = calculer_matrice_scores(0.5, 0.5)
        m_haut = calculer_matrice_scores(3.0, 0.5)
        # Avec lambda=3.0, P(home >= 2) doit être plus élevé
        p_bas = sum(v for k, v in m_bas.items() if int(k.split("-")[0]) >= 2)
        p_haut = sum(v for k, v in m_haut.items() if int(k.split("-")[0]) >= 2)
        assert p_haut > p_bas


class TestDeriveProbs:
    def _matrice(self, lam=1.5, mu=1.2):
        from backend.models.algorithms.dixon_coles import calculer_matrice_scores
        return calculer_matrice_scores(lam, mu)

    def test_somme_1x2_proche_1(self):
        from backend.models.algorithms.dixon_coles import deriver_probabilites_marches
        m = self._matrice()
        probs = deriver_probabilites_marches(m)
        total = probs["prob_home_win"] + probs["prob_draw"] + probs["prob_away_win"]
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_over25_coherent(self):
        from backend.models.algorithms.dixon_coles import deriver_probabilites_marches
        m = self._matrice()
        probs = deriver_probabilites_marches(m)
        # over25 = P(total > 2) doit être entre over15 et over35
        assert probs["prob_over15"] >= probs["prob_over25"] >= probs["prob_over35"]

    def test_btts_coherent(self):
        from backend.models.algorithms.dixon_coles import deriver_probabilites_marches
        m = self._matrice()
        probs = deriver_probabilites_marches(m)
        assert 0.0 < probs["prob_btts"] < 1.0

    def test_lambda_faible_over25_plus_rare(self):
        """Avec lambda=mu=0.5, over25 doit être improbable."""
        from backend.models.algorithms.dixon_coles import (
            calculer_matrice_scores, deriver_probabilites_marches,
        )
        m = calculer_matrice_scores(0.5, 0.5)
        probs = deriver_probabilites_marches(m)
        assert probs["prob_over25"] < 0.2

    def test_lambda_eleve_over25_probable(self):
        """Avec lambda=mu=2.5, over25 doit être probable."""
        from backend.models.algorithms.dixon_coles import (
            calculer_matrice_scores, deriver_probabilites_marches,
        )
        m = calculer_matrice_scores(2.5, 2.5)
        probs = deriver_probabilites_marches(m)
        assert probs["prob_over25"] > 0.7


# ─────────────────────────────────────────────────────────────────────────────
# MetaModel
# ─────────────────────────────────────────────────────────────────────────────

class TestMetaModelFallback:
    """Tests pour le fallback sur poids fixes quand stacking indisponible."""

    def test_prediction_moyenne_ponderee(self):
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        pred_xgb = np.array([0.6, 0.7])
        pred_rf = np.array([0.5, 0.6])
        pred_lr = np.array([0.4, 0.5])
        result = meta.predire(pred_xgb, pred_rf, pred_lr)
        # Poids : XGB=0.50, RF=0.30, LR=0.20
        expected = pred_xgb * 0.50 + pred_rf * 0.30 + pred_lr * 0.20
        np.testing.assert_allclose(result, expected, atol=1e-6)

    def test_prediction_sans_lr(self):
        """Renormalise les poids si LR manquant."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        pred_xgb = np.array([0.6])
        pred_rf = np.array([0.5])
        result = meta.predire(pred_xgb, pred_rf, None)
        # Poids renormalisés : XGB=0.50/(0.50+0.30), RF=0.30/(0.50+0.30)
        poids_xgb = 0.50 / 0.80
        poids_rf = 0.30 / 0.80
        expected = pred_xgb * poids_xgb + pred_rf * poids_rf
        np.testing.assert_allclose(result, expected, atol=1e-6)

    def test_prediction_xgb_seul(self):
        """Si seul XGB disponible, retourne XGB."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        pred_xgb = np.array([0.65])
        result = meta.predire(pred_xgb, None, None)
        np.testing.assert_allclose(result, pred_xgb, atol=1e-6)

    def test_prediction_aucun_modele(self):
        """Sans aucune prédiction, retourne None."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        assert meta.predire(None, None, None) is None

    def test_clipping_bornes(self):
        """Les prédictions doivent rester dans [0, 1]."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        pred = np.array([1.5, -0.3, 0.5])
        result = meta.predire(pred, None, None)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_nan_remplace_par_05(self):
        """Les NaN dans les prédictions sont remplacés par 0.5 (neutre)."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        pred = np.array([np.nan, 0.6])
        result = meta.predire(pred, None, None)
        assert not np.isnan(result).any()
        # Le premier élément était NaN → remplacé par 0.5
        assert result[0] == pytest.approx(0.5, abs=1e-6)


class TestMetaModelStacking:
    """Tests pour le méta-apprenant de stacking."""

    def _donnees_synthetiques(self, n=500, seed=42):
        rng = np.random.default_rng(seed)
        y = rng.integers(0, 2, size=n).astype(float)
        # Prédictions corrélées à y avec bruit
        oof_xgb = np.clip(y + rng.normal(0, 0.3, n), 0, 1)
        oof_rf = np.clip(y + rng.normal(0, 0.4, n), 0, 1)
        oof_lr = np.clip(y + rng.normal(0, 0.5, n), 0, 1)
        return oof_xgb, oof_rf, oof_lr, y

    def test_stacking_entraine_et_predit(self):
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        oof_xgb, oof_rf, oof_lr, y = self._donnees_synthetiques()
        meta.entrainer_stacking(oof_xgb, oof_rf, oof_lr, y)
        assert meta._stacking_model is not None
        # Prédiction sur nouvelles données
        pred = meta.predire(
            np.array([0.6, 0.4]),
            np.array([0.55, 0.45]),
            np.array([0.5, 0.5]),
        )
        assert pred is not None
        assert len(pred) == 2
        assert pred.min() >= 0.0
        assert pred.max() <= 1.0

    def test_stacking_ignore_si_classe_unique(self):
        """Stacking refusé si y contient une seule classe."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        n = 100
        y_unique = np.zeros(n)
        meta.entrainer_stacking(
            np.random.rand(n),
            np.random.rand(n),
            np.random.rand(n),
            y_unique,
        )
        assert meta._stacking_model is None


class TestMetaModelCalibration:
    """Tests pour la calibration Platt scaling."""

    def test_calibration_modifie_probas(self):
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        rng = np.random.default_rng(0)
        meta = MetaModel("over25")
        n = 200
        probas = rng.uniform(0.1, 0.9, n)
        y = (probas > 0.5).astype(int)
        meta.calibrer(probas, y)
        assert meta.est_calibre is True
        calibrees = meta.appliquer_calibration(probas)
        # Les probabilités calibrées doivent être dans [0.01, 0.99]
        assert calibrees.min() >= 0.01
        assert calibrees.max() <= 0.99

    def test_calibration_ignoree_si_classe_unique(self):
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        meta.calibrer(np.array([0.3, 0.6, 0.5]), np.array([0, 0, 0]))
        assert meta.est_calibre is False

    def test_fallback_sans_calibration(self):
        """Sans calibrateur, appliquer_calibration retourne les probas clippées."""
        from backend.models.algorithms.ensemble.meta_model import MetaModel
        meta = MetaModel("over25")
        probas = np.array([0.3, 0.7, 0.5])
        result = meta.appliquer_calibration(probas)
        np.testing.assert_allclose(result, np.clip(probas, 0.01, 0.99), atol=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# Accumulateur — fusion DC/ML
# ─────────────────────────────────────────────────────────────────────────────

class TestFusionDCML:
    """Tests pour GenerateurPronostics._fusionner_probabilites."""

    def _gen(self):
        from unittest.mock import MagicMock
        from backend.analysis.accumulateur import GenerateurPronostics
        gen = GenerateurPronostics.__new__(GenerateurPronostics)
        gen.conn = MagicMock()
        return gen

    def test_sans_pred_dc_retourne_vide(self):
        gen = self._gen()
        result = gen._fusionner_probabilites(None, {})
        assert result == {}

    def test_sans_pred_ml_retourne_dc(self):
        gen = self._gen()
        pred_dc = {
            "prob_home_win": 0.45,
            "prob_draw": 0.30,
            "prob_away_win": 0.25,
            "prob_over25": 0.52,
            "prob_btts": 0.48,
        }
        result = gen._fusionner_probabilites(pred_dc, {})
        assert result["prob_home_win"] == pytest.approx(0.45)
        assert result["prob_over25"] == pytest.approx(0.52)

    def test_1x2_poids_dc_dominant(self):
        """Les marchés 1x2 utilisent DC=80%, ML=20% — DC très majoritaire."""
        gen = self._gen()
        pred_dc = {
            "prob_home_win": 0.45, "prob_draw": 0.28, "prob_away_win": 0.27,
            "prob_over25": 0.50, "prob_btts": 0.48,
        }
        pred_ml = {
            "ml_prob_home_win": 0.45,  # même valeur → résultat = DC
            "ml_prob_draw": 0.28,
            "ml_prob_away_win": 0.27,
            "ml_prob_over25": 0.60,
        }
        result = gen._fusionner_probabilites(pred_dc, pred_ml)
        # Quand ML == DC, la fusion doit retourner la même valeur
        assert result["prob_home_win"] == pytest.approx(0.45)
        assert result["prob_draw"] == pytest.approx(0.28)
        assert result["prob_away_win"] == pytest.approx(0.27)

    def test_over25_fusion_ponderee(self):
        """over25 : DC=0.55, ML=0.45."""
        gen = self._gen()
        pred_dc = {"prob_over25": 0.50}
        pred_ml = {"ml_prob_over25": 0.70}
        result = gen._fusionner_probabilites(pred_dc, pred_ml)
        expected = 0.50 * 0.55 + 0.70 * 0.45
        assert result["prob_over25"] == pytest.approx(expected, abs=1e-4)

    def test_btts_fusion_ponderee(self):
        """btts : DC=0.55, ML=0.45."""
        gen = self._gen()
        pred_dc = {"prob_btts": 0.48}
        pred_ml = {"ml_prob_btts": 0.60}
        result = gen._fusionner_probabilites(pred_dc, pred_ml)
        expected = 0.48 * 0.55 + 0.60 * 0.45
        assert result["prob_btts"] == pytest.approx(expected, abs=1e-4)

    def test_over15_fusion_ponderee(self):
        """over15 : DC=0.65, ML=0.35."""
        gen = self._gen()
        pred_dc = {"prob_over15": 0.70}
        pred_ml = {"ml_prob_over15": 0.80}
        result = gen._fusionner_probabilites(pred_dc, pred_ml)
        expected = 0.70 * 0.65 + 0.80 * 0.35
        assert result["prob_over15"] == pytest.approx(expected, abs=1e-4)

    def test_over35_present_dans_resultat(self):
        """over35 est un marché actif — doit apparaître dans la fusion si fourni par DC."""
        gen = self._gen()
        pred_dc = {"prob_over25": 0.50, "prob_over35": 0.25, "prob_btts": 0.48}
        pred_ml = {"ml_prob_over25": 0.55}
        result = gen._fusionner_probabilites(pred_dc, pred_ml)
        assert "prob_over35" in result

    def test_over15_ht_present_dans_resultat(self):
        """over15_ht activé (78% disponibilité en DB) — doit apparaître dans la fusion."""
        gen = self._gen()
        pred_dc = {"prob_home_win": 0.45, "dc_lambda": 1.3, "dc_mu": 1.1}
        pred_ml = {"ml_prob_over15_ht": 0.62}
        result = gen._fusionner_probabilites(pred_dc, pred_ml)
        assert "prob_over15_ht" in result
        assert result["prob_over15_ht"] == pytest.approx(0.62, abs=1e-4)
