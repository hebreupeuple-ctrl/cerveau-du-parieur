import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.analysis.accumulateur import GenerateurPronostics
from backend.api.router import app
from backend.core.config import settings
from backend.database.connection import fermer_connexion, obtenir_connexion
from backend.database.migrations import appliquer_migrations
from backend.scheduler.locks import DistributedJobLockService
from backend.scheduler.tasks.automation import (
    _backfill_features_historiques_sync,
    obtenir_resume_features_historiques,
)


class SystemSafetyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_database_path = settings.DATABASE_PATH
        self.original_database_url = settings.DATABASE_URL
        self.original_scheduler_enabled = settings.SCHEDULER_ENABLED
        self.original_secret_key = settings.SECRET_KEY
        self.original_admin_emails = settings.ADMIN_EMAILS

        settings.DATABASE_PATH = os.path.join(
            self.tempdir.name,
            "test.db",
        )
        settings.DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"
        settings.SCHEDULER_ENABLED = False
        settings.SECRET_KEY = "test-secret-key"
        settings.ADMIN_EMAILS = "admin@example.com"

        fermer_connexion()
        conn = obtenir_connexion()
        appliquer_migrations(conn)

    def tearDown(self):
        fermer_connexion()
        settings.DATABASE_PATH = self.original_database_path
        settings.DATABASE_URL = self.original_database_url
        settings.SCHEDULER_ENABLED = self.original_scheduler_enabled
        settings.SECRET_KEY = self.original_secret_key
        settings.ADMIN_EMAILS = self.original_admin_emails
        self.tempdir.cleanup()

    def _register(self, client: TestClient, email: str, password: str):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "initial_bankroll": 150,
                "kelly_fraction": 0.125,
            },
        )
        self.assertEqual(response.status_code, 201)

    def _login(self, client: TestClient, email: str, password: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
                "device_fingerprint": f"device::{email}",
                "device_name": "Tests",
                "platform": "test",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["access_token"]

    def test_logout_revokes_current_token(self):
        with TestClient(app) as client:
            self._register(client, "admin@example.com", "Password123!")
            token = self._login(client, "admin@example.com", "Password123!")
            headers = {"Authorization": f"Bearer {token}"}

            me_before = client.get("/api/v1/auth/me", headers=headers)
            self.assertEqual(me_before.status_code, 200)

            logout = client.post("/api/v1/auth/logout", headers=headers)
            self.assertEqual(logout.status_code, 204)

            me_after = client.get("/api/v1/auth/me", headers=headers)
            self.assertEqual(me_after.status_code, 401)

    def test_manual_system_jobs_require_admin(self):
        with TestClient(app) as client:
            self._register(client, "admin@example.com", "Password123!")
            self._register(client, "user@example.com", "Password123!")
            token = self._login(client, "user@example.com", "Password123!")
            headers = {"Authorization": f"Bearer {token}"}

            response = client.post(
                "/api/v1/system/manual-retrain",
                headers=headers,
            )
            self.assertEqual(response.status_code, 403)

    def test_place_bet_rejects_stake_above_bankroll(self):
        with TestClient(app) as client:
            self._register(client, "admin@example.com", "Password123!")
            token = self._login(client, "admin@example.com", "Password123!")
            headers = {"Authorization": f"Bearer {token}"}

            conn = obtenir_connexion()
            conn.execute(
                """
                INSERT INTO leagues (
                    id, footystats_id, name, country, tier, group_type, priority
                ) VALUES (1, 101, 'Test League', 'Test', 1, 'test', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO seasons (
                    id, footystats_id, league_id, name, year,
                    start_date, end_date, status
                ) VALUES (1, 201, 1, '2026', 2026, '2026-01-01', '2026-12-31', 'active')
                """
            )
            conn.execute(
                """
                INSERT INTO teams (id, footystats_id, name, country)
                VALUES (1, 301, 'Home', 'Test'), (2, 302, 'Away', 'Test')
                """
            )
            conn.execute(
                """
                INSERT INTO matches (
                    id, footystats_id, season_id, league_id,
                    home_team_id, away_team_id,
                    match_date, match_timestamp, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    401,
                    1,
                    1,
                    1,
                    2,
                    "2026-03-25",
                    int(time.time()) + 7200,
                    "upcoming",
                ),
            )
            conn.execute(
                """
                INSERT INTO pronostics (
                    id, user_id, match_id, market,
                    model_probability, bookmaker_probability, probability_edge,
                    expected_value, reference_bookmaker, reference_odds,
                    confidence_score, kelly_fraction_used, kelly_raw,
                    recommended_stake, bankroll_at_recommendation, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    1,
                    "over25",
                    0.65,
                    0.5,
                    0.15,
                    0.08,
                    "footystats",
                    2.1,
                    0.72,
                    0.125,
                    0.08,
                    10.0,
                    150.0,
                    "pending",
                ),
            )
            conn.commit()

            response = client.post(
                "/api/v1/pronostics/1/place",
                headers=headers,
                json={
                    "actual_stake": 500,
                    "actual_odds": 2.1,
                },
            )
            self.assertEqual(response.status_code, 409)

            bankroll = conn.execute(
                "SELECT current_bankroll FROM users WHERE id = 1"
            ).fetchone()["current_bankroll"]
            self.assertEqual(bankroll, 150.0)

    def test_distributed_lock_prevents_double_acquire(self):
        service_a = DistributedJobLockService(owner_id="a", lease_seconds=60)
        service_b = DistributedJobLockService(owner_id="b", lease_seconds=60)

        token = service_a.acquire("system_pipeline")
        self.assertIsNotNone(token)
        self.assertIsNone(service_b.acquire("system_pipeline"))

        service_a.release("system_pipeline", token)
        self.assertIsNotNone(service_b.acquire("system_pipeline"))

    def test_new_user_gets_pronostics_on_first_today_fetch(self):
        with TestClient(app) as client:
            self._register(client, "admin@example.com", "Password123!")
            token = self._login(client, "admin@example.com", "Password123!")
            headers = {"Authorization": f"Bearer {token}"}

            conn = obtenir_connexion()
            conn.execute(
                """
                INSERT INTO leagues (
                    id, footystats_id, name, country, tier, group_type, priority
                ) VALUES (1, 101, 'Test League', 'Test', 1, 'test', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO seasons (
                    id, footystats_id, league_id, name, year,
                    start_date, end_date, status
                ) VALUES (1, 201, 1, '2026', 2026, '2026-01-01', '2026-12-31', 'active')
                """
            )
            conn.execute(
                """
                INSERT INTO teams (id, footystats_id, name, country)
                VALUES (1, 301, 'Home', 'Test'), (2, 302, 'Away', 'Test')
                """
            )
            conn.execute(
                """
                INSERT INTO matches (
                    id, footystats_id, season_id, league_id,
                    home_team_id, away_team_id,
                    match_date, match_timestamp, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    401,
                    1,
                    1,
                    1,
                    2,
                    "2026-03-25",
                    int(time.time()) + 7200,
                    "upcoming",
                ),
            )
            conn.commit()

            def fake_generation(
                conn,
                user,
                generateur=None,
                max_pronostics=10,
                replace_pending=True,
                commit=False,
            ):
                conn.execute(
                    """
                    INSERT INTO pronostics (
                        user_id, match_id, market,
                        model_probability, bookmaker_probability, probability_edge,
                        expected_value, reference_bookmaker, reference_odds,
                        confidence_score, kelly_fraction_used, kelly_raw,
                        recommended_stake, bankroll_at_recommendation, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        user["id"],
                        1,
                        "over25",
                        0.65,
                        0.50,
                        0.15,
                        0.08,
                        "footystats",
                        2.10,
                        0.72,
                        0.125,
                        0.08,
                        10.0,
                        user["current_bankroll"],
                    ),
                )
                if commit:
                    conn.commit()
                return {
                    "user_id": user["id"],
                    "email": user["email"],
                    "inserted": 1,
                    "generated": 1,
                }

            with patch(
                "backend.scheduler.tasks.automation.generer_et_sauvegarder_pronostics_utilisateur",
                side_effect=fake_generation,
            ) as mocked_generation:
                response = client.get(
                    "/api/v1/pronostics/today",
                    headers=headers,
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                len(response.json()["data"]["pronostics"]),
                1,
            )
            self.assertEqual(mocked_generation.call_count, 1)

    def test_register_assigns_existing_leagues_when_none_active(self):
        conn = obtenir_connexion()
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (1, 101, 'Inactive League', 'Test', 1, 'test', 1, 0)
            """
        )
        conn.commit()

        with TestClient(app) as client:
            self._register(client, "inactive@example.com", "Password123!")

        conn = obtenir_connexion()
        user_leagues = conn.execute(
            """
            SELECT COUNT(*)
            FROM user_leagues
            WHERE user_id = 1
            """
        ).fetchone()[0]
        self.assertEqual(user_leagues, 1)

    def test_league_fallback_uses_all_leagues_when_user_and_active_sets_are_empty(self):
        conn = obtenir_connexion()
        conn.execute(
            """
            INSERT INTO users (
                id, email, password_hash,
                initial_bankroll, current_bankroll, kelly_fraction
            ) VALUES (1, 'fallback@example.com', 'hash', 150, 150, 0.125)
            """
        )
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (1, 101, 'League A', 'Test', 1, 'test', 1, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (2, 102, 'League B', 'Test', 1, 'test', 1, 0)
            """
        )
        conn.commit()

        generateur = GenerateurPronostics(conn)
        leagues = generateur._obtenir_leagues_autorisees(1)
        self.assertEqual(leagues, {1, 2})

    @patch("backend.scheduler.tasks.automation.FeaturePipeline")
    def test_backfill_only_processes_active_leagues(self, pipeline_cls):
        conn = obtenir_connexion()
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (1, 101, 'Active League', 'Test', 1, 'test', 1, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (2, 102, 'Inactive League', 'Test', 1, 'test', 1, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO teams (id, footystats_id, name, country)
            VALUES
                (1, 301, 'Home 1', 'Test'),
                (2, 302, 'Away 1', 'Test'),
                (3, 303, 'Home 2', 'Test'),
                (4, 304, 'Away 2', 'Test')
            """
        )
        conn.execute(
            """
            INSERT INTO seasons (
                id, footystats_id, league_id, name, year,
                start_date, end_date, status
            ) VALUES
                (1, 201, 1, '2026 Active', 2026, '2026-01-01', '2026-12-31', 'active'),
                (2, 202, 2, '2026 Inactive', 2026, '2026-01-01', '2026-12-31', 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO matches (
                id, footystats_id, season_id, league_id,
                home_team_id, away_team_id,
                match_date, match_timestamp, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                401,
                1,
                1,
                1,
                2,
                "2026-03-20",
                now - 7200,
                "complete",
            ),
        )
        conn.execute(
            """
            INSERT INTO matches (
                id, footystats_id, season_id, league_id,
                home_team_id, away_team_id,
                match_date, match_timestamp, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                402,
                2,
                2,
                3,
                4,
                "2026-03-21",
                now - 3600,
                "complete",
            ),
        )
        conn.commit()

        match_ids = []
        pipeline = pipeline_cls.return_value

        def fake_calculer_et_sauvegarder(**kwargs):
            match_ids.append(kwargs["match_id"])
            return True

        pipeline.calculer_et_sauvegarder.side_effect = fake_calculer_et_sauvegarder

        resultat = _backfill_features_historiques_sync(batch_size=10)

        self.assertEqual(resultat["processed"], 1)
        self.assertEqual(resultat["ok"], 1)
        self.assertEqual(match_ids, [1])

    def test_historical_feature_summary_only_counts_active_leagues(self):
        conn = obtenir_connexion()
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (1, 101, 'Active League', 'Test', 1, 'test', 1, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO leagues (
                id, footystats_id, name, country, tier, group_type, priority, is_active
            ) VALUES (2, 102, 'Inactive League', 'Test', 1, 'test', 1, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO teams (id, footystats_id, name, country)
            VALUES
                (1, 301, 'Home 1', 'Test'),
                (2, 302, 'Away 1', 'Test'),
                (3, 303, 'Home 2', 'Test'),
                (4, 304, 'Away 2', 'Test')
            """
        )
        conn.execute(
            """
            INSERT INTO seasons (
                id, footystats_id, league_id, name, year,
                start_date, end_date, status
            ) VALUES
                (1, 201, 1, '2026 Active', 2026, '2026-01-01', '2026-12-31', 'active'),
                (2, 202, 2, '2026 Inactive', 2026, '2026-01-01', '2026-12-31', 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO matches (
                id, footystats_id, season_id, league_id,
                home_team_id, away_team_id,
                match_date, match_timestamp, status
            ) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?),
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                401,
                1,
                1,
                1,
                2,
                "2026-03-20",
                now - 7200,
                "complete",
                2,
                402,
                2,
                2,
                3,
                4,
                "2026-03-21",
                now - 3600,
                "complete",
            ),
        )
        conn.execute(
            """
            INSERT INTO match_features (match_id)
            VALUES (?), (?)
            """,
            (
                1,
                2,
            ),
        )
        conn.commit()

        resultat = obtenir_resume_features_historiques(conn)

        self.assertEqual(resultat["matches_complete"], 1)
        self.assertEqual(resultat["features_historiques_calculees"], 1)
        self.assertEqual(resultat["features_historiques_manquantes"], 0)
        self.assertEqual(resultat["historical_backfill_coverage_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
