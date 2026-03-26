"""
Tests E2E — Flux complet du système.

Couvre :
1. Inscription + connexion
2. Accès /me et profil utilisateur
3. Génération pronostics (mock ML + Dixon-Coles)
4. Placement d'un pari (placed)
5. Résolution automatique (won/lost)
6. Mise à jour bankroll
7. Rate limiting (429 sur auth)
8. Accès endpoints système admin-only
"""

import os
import time
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.api.router import app
from backend.core.config import settings
from backend.database.connection import fermer_connexion, obtenir_connexion
from backend.database.migrations import appliquer_migrations


class TestFluxComplet(unittest.TestCase):
    """Tests E2E couvrant le flux complet du système."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self._orig_db_path = settings.DATABASE_PATH
        self._orig_db_url = settings.DATABASE_URL
        self._orig_scheduler = settings.SCHEDULER_ENABLED
        self._orig_secret = settings.SECRET_KEY
        self._orig_admin = settings.ADMIN_EMAILS
        self._orig_env = settings.ENVIRONMENT

        settings.DATABASE_PATH = os.path.join(self.tempdir.name, "e2e_test.db")
        settings.DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"
        settings.SCHEDULER_ENABLED = False
        settings.SECRET_KEY = "e2e-test-secret-key-at-least-32-chars-long"
        settings.ADMIN_EMAILS = "admin@test.com"
        settings.ENVIRONMENT = "test"

        fermer_connexion()
        conn = obtenir_connexion()
        appliquer_migrations(conn)
        self._inserer_donnees_test(conn)

    def tearDown(self):
        fermer_connexion()
        settings.DATABASE_PATH = self._orig_db_path
        settings.DATABASE_URL = self._orig_db_url
        settings.SCHEDULER_ENABLED = self._orig_scheduler
        settings.SECRET_KEY = self._orig_secret
        settings.ADMIN_EMAILS = self._orig_admin
        settings.ENVIRONMENT = self._orig_env
        self.tempdir.cleanup()

    def _inserer_donnees_test(self, conn):
        """Insère une ligue, une saison, deux équipes et un match pour les tests."""
        conn.execute("""
            INSERT OR IGNORE INTO leagues
                (id, footystats_id, name, country, tier, group_type,
                 season_start_month, season_end_month, is_active, priority)
            VALUES (1, 9999, 'Test League', 'TestLand', 1, 'major_european', 8, 5, 1, 1)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO seasons
                (id, footystats_id, league_id, name, year, start_date, end_date, status)
            VALUES (1, 8888, 1, 'Test 2025/26', 2025, '2025-08-01', '2026-05-31', 'active')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO teams
                (id, footystats_id, name, country)
            VALUES
                (1, 1001, 'Home FC', 'TestLand'),
                (2, 1002, 'Away FC', 'TestLand')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO matches
                (id, footystats_id, season_id, league_id,
                 home_team_id, away_team_id,
                 match_date, match_timestamp, game_week, status)
            VALUES (1, 7777, 1, 1, 1, 2,
                    '2099-12-31', ?, 10, 'upcoming')
        """, (int(time.time()) + 24 * 3600,))
        conn.execute("""
            INSERT OR IGNORE INTO odds
                (match_id, bookmaker, bookmaker_tier, collected_timestamp,
                 odds_home, odds_draw, odds_away,
                 odds_over15, odds_under15,
                 odds_over25, odds_under25,
                 odds_btts_yes, odds_btts_no,
                 is_closing)
            VALUES (1, 'pinnacle', 1, ?, 2.10, 3.40, 3.60,
                    1.30, 3.50,
                    1.95, 1.90,
                    1.85, 1.95,
                    1)
        """, (int(time.time()),))
        conn.commit()

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _register(self, client: TestClient, email: str, password: str,
                  bankroll: float = 200.0) -> None:
        r = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "initial_bankroll": bankroll,
            "kelly_fraction": 0.125,
        })
        self.assertEqual(r.status_code, 201, r.text)

    def _login(self, client: TestClient, email: str, password: str) -> str:
        r = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password,
            "device_fingerprint": f"fp::{email}",
            "device_name": "E2E Test",
            "platform": "test",
        })
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["data"]["access_token"]

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ─────────────────────────────────────────────────────────────
    # Test 1 : Inscription + connexion + /me
    # ─────────────────────────────────────────────────────────────

    def test_01_inscription_login_me(self):
        with TestClient(app) as client:
            self._register(client, "user@test.com", "Password123!", bankroll=300.0)
            token = self._login(client, "user@test.com", "Password123!")
            r = client.get("/api/v1/auth/me", headers=self._headers(token))
            self.assertEqual(r.status_code, 200)
            data = r.json()["data"]
            self.assertEqual(data["email"], "user@test.com")
            self.assertAlmostEqual(data["current_bankroll"], 300.0)

    # ─────────────────────────────────────────────────────────────
    # Test 2 : Double inscription → 409
    # ─────────────────────────────────────────────────────────────

    def test_02_double_inscription_409(self):
        with TestClient(app) as client:
            self._register(client, "dup@test.com", "Password123!")
            r = client.post("/api/v1/auth/register", json={
                "email": "dup@test.com",
                "password": "Password123!",
                "initial_bankroll": 100,
                "kelly_fraction": 0.125,
            })
            self.assertEqual(r.status_code, 409)

    # ─────────────────────────────────────────────────────────────
    # Test 3 : Mauvais password → 401
    # ─────────────────────────────────────────────────────────────

    def test_03_mauvais_password_401(self):
        with TestClient(app) as client:
            self._register(client, "bad@test.com", "GoodPassword123!")
            r = client.post("/api/v1/auth/login", json={
                "email": "bad@test.com",
                "password": "WrongPassword!",
                "device_fingerprint": "fp::bad",
                "device_name": "test",
                "platform": "test",
            })
            self.assertEqual(r.status_code, 401)

    # ─────────────────────────────────────────────────────────────
    # Test 4 : Logout révoque le token
    # ─────────────────────────────────────────────────────────────

    def test_04_logout_revoque_token(self):
        with TestClient(app) as client:
            self._register(client, "logout@test.com", "Password123!")
            token = self._login(client, "logout@test.com", "Password123!")
            h = self._headers(token)

            self.assertEqual(client.get("/api/v1/auth/me", headers=h).status_code, 200)
            self.assertEqual(client.post("/api/v1/auth/logout", headers=h).status_code, 204)
            self.assertEqual(client.get("/api/v1/auth/me", headers=h).status_code, 401)

    # ─────────────────────────────────────────────────────────────
    # Test 5 : Token absent → 401
    # ─────────────────────────────────────────────────────────────

    def test_05_sans_token_401(self):
        with TestClient(app) as client:
            r = client.get("/api/v1/auth/me")
            self.assertEqual(r.status_code, 401)

    # ─────────────────────────────────────────────────────────────
    # Test 6 : Génération pronostics du jour (mock ML + DC)
    # ─────────────────────────────────────────────────────────────

    def test_06_pronostics_du_jour(self):
        with TestClient(app) as client:
            self._register(client, "pronostic@test.com", "Password123!", bankroll=500.0)
            token = self._login(client, "pronostic@test.com", "Password123!")
            h = self._headers(token)

            mock_dc = {
                "prob_home_win": 0.50,
                "prob_draw": 0.25,
                "prob_away_win": 0.25,
                "prob_over15": 0.80,
                "prob_over25": 0.65,
                "prob_over45": 0.15,
                "prob_btts": 0.55,
                "prob_btts_no": 0.45,
                "score_matrix": {"2-1": 0.12, "1-0": 0.10},
            }
            mock_ml = {
                "ml_prob_over25": 0.70,
                "ml_prob_btts": 0.60,
                "ml_prob_over15": 0.82,
            }

            def _mock_charger(self):
                self.modeles = {"over25": True}

            with patch(
                "backend.models.algorithms.dixon_coles.DixonColesModel.predire_match",
                return_value=mock_dc,
            ), patch(
                "backend.models.trainer.ModelTrainer.predire",
                return_value=mock_ml,
            ), patch(
                "backend.models.trainer.ModelTrainer._charger_modeles",
                _mock_charger,
            ):
                r = client.get("/api/v1/pronostics/today", headers=h)

            # Peut retourner 200 avec liste vide si EV < seuil, c'est correct
            self.assertIn(r.status_code, (200,))
            data = r.json()
            self.assertIn("data", data)

    # ─────────────────────────────────────────────────────────────
    # Test 7 : Placement + résolution manuelle d'un pronostic
    # ─────────────────────────────────────────────────────────────

    def test_07_placement_et_resolution(self):
        with TestClient(app) as client:
            self._register(client, "pari@test.com", "Password123!", bankroll=200.0)
            token = self._login(client, "pari@test.com", "Password123!")
            h = self._headers(token)

            # Créer un pronostic pending manuellement en base
            conn = obtenir_connexion()
            user_row = conn.execute(
                "SELECT id FROM users WHERE email = 'pari@test.com'"
            ).fetchone()
            user_id = user_row["id"]

            conn.execute("""
                INSERT INTO pronostics
                    (user_id, match_id, market,
                     model_probability, bookmaker_probability, probability_edge,
                     expected_value, reference_bookmaker, reference_odds,
                     confidence_score, kelly_fraction_used, kelly_raw,
                     recommended_stake, bankroll_at_recommendation, status)
                VALUES (?, 1, 'over25',
                        0.68, 0.55, 0.13,
                        0.32, 'pinnacle', 1.95,
                        0.68, 0.125, 0.24,
                        25.0, 200.0, 'pending')
            """, (user_id,))
            conn.commit()

            pronostic_row = conn.execute(
                "SELECT id FROM pronostics WHERE user_id = ? AND market = 'over25'",
                (user_id,)
            ).fetchone()
            pronostic_id = pronostic_row["id"]

            # Placer le pari
            r_place = client.post(f"/api/v1/pronostics/{pronostic_id}/place", json={
                "actual_stake": 25.0,
                "actual_odds": 1.93,
            }, headers=h)
            self.assertEqual(r_place.status_code, 200, r_place.text)

            placed_row = conn.execute(
                "SELECT status, actual_stake FROM pronostics WHERE id = ?",
                (pronostic_id,)
            ).fetchone()
            self.assertEqual(placed_row["status"], "placed")
            self.assertAlmostEqual(placed_row["actual_stake"], 25.0)

            # Résolution manuelle : marquer le match complet avec score over25=True
            conn.execute("""
                UPDATE matches SET
                    status = 'complete',
                    home_goals = 2, away_goals = 2,
                    total_goals = 4,
                    over25 = 1,
                    updated_at = datetime('now', '+1 hour')
                WHERE id = 1
            """)
            conn.commit()

            r_resolve = client.post(f"/api/v1/pronostics/{pronostic_id}/resolve", json={
                "result": "won",
            }, headers=h)
            self.assertEqual(r_resolve.status_code, 200, r_resolve.text)

            resolved_row = conn.execute(
                "SELECT status, actual_profit FROM pronostics WHERE id = ?",
                (pronostic_id,)
            ).fetchone()
            self.assertEqual(resolved_row["status"], "won")
            self.assertGreater(resolved_row["actual_profit"], 0)

    # ─────────────────────────────────────────────────────────────
    # Test 8 : Performance summary accessible
    # ─────────────────────────────────────────────────────────────

    def test_08_performance_summary(self):
        with TestClient(app) as client:
            self._register(client, "perf@test.com", "Password123!")
            token = self._login(client, "perf@test.com", "Password123!")
            r = client.get("/api/v1/performance/summary", headers=self._headers(token))
            self.assertEqual(r.status_code, 200)
            data = r.json()["data"]
            self.assertIn("metrics", data)
            self.assertIn("roi", data["metrics"])
            self.assertIn("win_rate", data["metrics"])

    # ─────────────────────────────────────────────────────────────
    # Test 9 : Rate limiting 429 sur auth
    # ─────────────────────────────────────────────────────────────

    def test_09_rate_limiting_auth(self):
        # Activer temporairement le rate limiting pour ce test
        settings.ENVIRONMENT = "production"
        try:
            with TestClient(app) as client:
                # Envoyer 12 requêtes login (seuil = 10 / minute)
                blocked = False
                for i in range(12):
                    r = client.post("/api/v1/auth/login", json={
                        "email": f"ratelimit_{i}@test.com",
                        "password": "wrong",
                        "device_fingerprint": "same-ip-fp",
                        "device_name": "test",
                        "platform": "test",
                    })
                    if r.status_code == 429:
                        blocked = True
                        break
                self.assertTrue(blocked, "Le rate limiter devrait bloquer après 10 requêtes")
        finally:
            settings.ENVIRONMENT = "test"

    # ─────────────────────────────────────────────────────────────
    # Test 10 : Endpoint système admin-only → 403 pour user normal
    # ─────────────────────────────────────────────────────────────

    def test_10_system_admin_only(self):
        with TestClient(app) as client:
            # Le premier utilisateur inscrit devient admin automatiquement —
            # on inscrit d'abord un admin, puis un utilisateur normal.
            self._register(client, "admin@test.com", "Password123!")
            self._register(client, "normaluser@test.com", "Password123!")
            token = self._login(client, "normaluser@test.com", "Password123!")
            r = client.post(
                "/api/v1/system/manual-retrain",
                headers=self._headers(token),
            )
            self.assertEqual(r.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # Test 11 : Migration 014 — colonnes over35 absentes
    # ─────────────────────────────────────────────────────────────

    def test_11_migration_over35_colonnes_supprimees(self):
        """Vérifie que la migration 014 a supprimé les colonnes over35."""
        conn = obtenir_connexion()
        matches_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(matches)").fetchall()
        }
        odds_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(odds)").fetchall()
        }
        version = conn.execute(
            "SELECT sqlite_version()"
        ).fetchone()[0]
        parts = tuple(int(x) for x in version.split(".")[:3])
        if parts >= (3, 35, 0):
            self.assertNotIn("over35", matches_cols,
                             "Colonne over35 encore présente dans matches")
            self.assertNotIn("odds_over35", odds_cols,
                             "Colonne odds_over35 encore présente dans odds")

    # ─────────────────────────────────────────────────────────────
    # Test 12 : Ignoré pronostic → status ignored
    # ─────────────────────────────────────────────────────────────

    def test_12_ignorer_pronostic(self):
        with TestClient(app) as client:
            self._register(client, "ignore@test.com", "Password123!", bankroll=100.0)
            token = self._login(client, "ignore@test.com", "Password123!")
            h = self._headers(token)

            conn = obtenir_connexion()
            user_id = conn.execute(
                "SELECT id FROM users WHERE email = 'ignore@test.com'"
            ).fetchone()["id"]

            conn.execute("""
                INSERT INTO pronostics
                    (user_id, match_id, market,
                     model_probability, bookmaker_probability, probability_edge,
                     expected_value, reference_bookmaker, reference_odds,
                     confidence_score, kelly_fraction_used, kelly_raw,
                     recommended_stake, bankroll_at_recommendation, status)
                VALUES (?, 1, 'btts',
                        0.62, 0.54, 0.08,
                        0.15, 'pinnacle', 1.85,
                        0.62, 0.125, 0.18,
                        12.0, 100.0, 'pending')
            """, (user_id,))
            conn.commit()

            pronostic_id = conn.execute(
                "SELECT id FROM pronostics WHERE user_id = ? AND market = 'btts'",
                (user_id,)
            ).fetchone()["id"]

            r = client.post(f"/api/v1/pronostics/{pronostic_id}/ignore", json={
                "reason": "Trop de risque",
            }, headers=h)
            self.assertEqual(r.status_code, 200, r.text)

            status = conn.execute(
                "SELECT status FROM pronostics WHERE id = ?",
                (pronostic_id,)
            ).fetchone()["status"]
            self.assertEqual(status, "ignored")

    # ─────────────────────────────────────────────────────────────
    # Test 13 : Résolution automatique perte (lost)
    # ─────────────────────────────────────────────────────────────

    def test_13_resolution_automatique_perte(self):
        """Auto-résolution : over25 avec score 0-0 → lost, bankroll diminue."""
        from backend.scheduler.tasks.automation import _auto_resoudre_pronostics_sync

        conn = obtenir_connexion()

        # Créer un user
        conn.execute("""
            INSERT OR IGNORE INTO users
                (email, password_hash, initial_bankroll, current_bankroll,
                 kelly_fraction, min_confidence_simple, min_confidence_combine,
                 min_ev_threshold, min_prob_edge, urgency_threshold)
            VALUES ('auto@test.com', 'hash', 100.0, 100.0,
                    0.125, 0.60, 0.65, 0.03, 0.05, 0.85)
        """)
        conn.commit()
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = 'auto@test.com'"
        ).fetchone()["id"]

        # Match terminé avec score 0-0 (over25=False)
        # On fixe match_timestamp dans le passé pour que la condition
        # "updated_at > match_timestamp" soit vraie
        conn.execute("""
            UPDATE matches SET
                status = 'complete',
                match_timestamp = strftime('%s', 'now', '-3 hours'),
                home_goals = 0, away_goals = 0, total_goals = 0,
                over25 = 0,
                updated_at = datetime('now')
            WHERE id = 1
        """)

        # Pronostic placed — on simule aussi la déduction de la mise en bankroll
        # (comme le ferait l'endpoint /place qui réduit la bankroll au moment du placement)
        conn.execute(
            "UPDATE users SET current_bankroll = 80.0 WHERE id = ?", (user_id,)
        )
        conn.execute("""
            INSERT INTO pronostics
                (user_id, match_id, market,
                 model_probability, bookmaker_probability, probability_edge,
                 expected_value, reference_bookmaker, reference_odds,
                 confidence_score, kelly_fraction_used, kelly_raw,
                 recommended_stake, bankroll_at_recommendation,
                 status, actual_stake, actual_odds, placed_at)
            VALUES (?, 1, 'over25',
                    0.65, 0.52, 0.13,
                    0.27, 'pinnacle', 1.90,
                    0.65, 0.125, 0.20,
                    20.0, 100.0,
                    'placed', 20.0, 1.90, datetime('now'))
        """, (user_id,))
        conn.commit()

        result = _auto_resoudre_pronostics_sync()
        self.assertGreaterEqual(result["resolved"], 1)

        # Relire via une nouvelle connexion pour éviter le cache WAL
        from backend.database.connection import creer_connexion
        conn2 = creer_connexion()
        pronostic = conn2.execute(
            "SELECT status, actual_profit FROM pronostics WHERE user_id = ? AND market = 'over25'",
            (user_id,)
        ).fetchone()
        self.assertEqual(pronostic["status"], "lost")
        self.assertAlmostEqual(pronostic["actual_profit"], -20.0)

        bankroll = conn2.execute(
            "SELECT current_bankroll FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()["current_bankroll"]
        # La bankroll reste à 80 — la mise avait déjà été déduite au placement,
        # en cas de perte l'auto-résolution ne change pas la bankroll (retour = 0).
        self.assertAlmostEqual(bankroll, 80.0)
        conn2.close()


class TestCacheMatchFeatures(unittest.TestCase):
    """Tests unitaires pour la logique de cache dans l'accumulateur."""

    def _make_gen(self):
        from unittest.mock import MagicMock
        from backend.analysis.accumulateur import GenerateurPronostics
        gen = GenerateurPronostics.__new__(GenerateurPronostics)
        gen.conn = MagicMock()
        gen.dc_model = MagicMock()
        gen.ml_trainer = MagicMock()
        gen.feature_pipeline = MagicMock()
        gen._modeles_charges = True
        return gen

    def test_cache_utilise_si_recents(self):
        """Les features calculées il y a < 2h doivent éviter le recalcul."""
        from datetime import datetime, timezone
        gen = self._make_gen()

        now_ts = int(time.time())
        # Features calculées il y a 30 minutes
        calculated_at = datetime.fromtimestamp(now_ts - 1800, tz=timezone.utc).isoformat()

        features_row = MagicMock()
        features_row["calculated_at"] = calculated_at
        features_row.__getitem__ = lambda self, k: calculated_at if k == "calculated_at" else None

        gen.conn.execute.return_value.fetchone.side_effect = [
            # match row
            MagicMock(**{
                "__getitem__": lambda s, k: {
                    "status": "upcoming",
                    "match_timestamp": now_ts + 3600,
                    "home_team_id": 1,
                    "away_team_id": 2,
                    "league_id": 1,
                    "game_week": 10,
                    "league_name": "Test",
                }.get(k),
            }),
            # features_row
            features_row,
        ]

        # Le pipeline ne doit PAS être appelé si le cache est frais
        gen.feature_pipeline.calculer_features_match = MagicMock()
        gen.dc_model.predire_match = MagicMock(return_value=None)

        gen.generer_pour_match(
            match_id=1, user_id=1,
            bankroll=200.0, bankroll_initiale=200.0,
        )

        gen.feature_pipeline.calculer_features_match.assert_not_called()

    def test_cache_ignore_si_vieux(self):
        """Les features calculées il y a > 2h doivent être recalculées."""
        from datetime import datetime, timezone
        gen = self._make_gen()

        now_ts = int(time.time())
        # Features calculées il y a 3h
        calculated_at = datetime.fromtimestamp(now_ts - 10800, tz=timezone.utc).isoformat()

        features_row = MagicMock()
        features_row["calculated_at"] = calculated_at

        gen.conn.execute.return_value.fetchone.side_effect = [
            MagicMock(**{
                "__getitem__": lambda s, k: {
                    "status": "upcoming",
                    "match_timestamp": now_ts + 3600,
                    "home_team_id": 1,
                    "away_team_id": 2,
                    "league_id": 1,
                    "game_week": 10,
                    "league_name": "Test",
                }.get(k),
            }),
            features_row,
        ]

        gen.feature_pipeline.calculer_features_match = MagicMock(return_value=None)
        gen.dc_model.predire_match = MagicMock(return_value=None)

        gen.generer_pour_match(
            match_id=1, user_id=1,
            bankroll=200.0, bankroll_initiale=200.0,
        )

        gen.feature_pipeline.calculer_features_match.assert_called_once()


class TestRateLimiter(unittest.TestCase):
    """Tests unitaires pour le middleware de rate limiting."""

    def test_fenetre_glissante_bloque_apres_limite(self):
        from backend.api.middleware.rate_limiter import RateLimiterMiddleware
        from collections import deque

        # Simuler un bucket plein (limite = 5)
        bucket = deque()
        now = time.time()
        for i in range(5):
            bucket.append(now - i * 0.1)  # 5 requêtes très récentes

        instance = object.__new__(RateLimiterMiddleware)
        autorise = instance._est_autorise(bucket, limit=5, window=60)
        self.assertFalse(autorise)

    def test_fenetre_glissante_autorise_apres_expiration(self):
        from backend.api.middleware.rate_limiter import RateLimiterMiddleware
        from collections import deque

        # 5 requêtes toutes expirées (il y a 120s, fenêtre = 60s)
        bucket = deque()
        now = time.time()
        for i in range(5):
            bucket.append(now - 120 - i)

        instance = object.__new__(RateLimiterMiddleware)
        autorise = instance._est_autorise(bucket, limit=5, window=60)
        self.assertTrue(autorise)


if __name__ == "__main__":
    unittest.main()
