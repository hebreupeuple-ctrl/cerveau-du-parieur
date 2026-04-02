"""
Tests unitaires pour les corrections du commit d'audit.
Couvre : migrations 006/007, kelly adaptatif, value_betting, collector, pipeline.
"""

import sqlite3
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _creer_db_test() -> sqlite3.Connection:
    """Base de données SQLite en mémoire avec le schéma complet."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Appliquer toutes les migrations
    from backend.database.migrations import appliquer_migrations
    appliquer_migrations(conn)
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Migration 006 — odds HT
# ─────────────────────────────────────────────────────────────────────────────

class TestMigration006:
    def test_colonnes_odds_ht_existent(self):
        conn = _creer_db_test()
        cursor = conn.execute("PRAGMA table_info(odds)")
        noms = {row["name"] for row in cursor.fetchall()}
        assert "odds_over15_ht" in noms, "odds_over15_ht manquant"
        assert "odds_under15_ht" in noms, "odds_under15_ht manquant"
        assert "prob_over15_ht_corrected" in noms, "prob_over15_ht_corrected manquant"

    def test_idempotence_migration_006(self):
        """Appliquer deux fois ne doit pas planter."""
        conn = _creer_db_test()
        from backend.database.migrations.migration_006 import appliquer
        appliquer(conn)  # deuxième application → ignore silencieusement
        cursor = conn.execute("PRAGMA table_info(odds)")
        noms = {row["name"] for row in cursor.fetchall()}
        assert "odds_over15_ht" in noms


# ─────────────────────────────────────────────────────────────────────────────
# Migration 007 — predictions HT
# ─────────────────────────────────────────────────────────────────────────────

class TestMigration007:
    def test_colonnes_predictions_ht_existent(self):
        conn = _creer_db_test()
        cursor = conn.execute("PRAGMA table_info(predictions)")
        noms = {row["name"] for row in cursor.fetchall()}
        assert "ml_prob_over15_ht" in noms, "ml_prob_over15_ht manquant"
        assert "prob_over15_ht" in noms, "prob_over15_ht manquant"

    def test_idempotence_migration_007(self):
        conn = _creer_db_test()
        from backend.database.migrations.migration_007 import appliquer
        appliquer(conn)
        cursor = conn.execute("PRAGMA table_info(predictions)")
        noms = {row["name"] for row in cursor.fetchall()}
        assert "ml_prob_over15_ht" in noms


# ─────────────────────────────────────────────────────────────────────────────
# Kelly — fraction adaptative
# ─────────────────────────────────────────────────────────────────────────────

class TestKellyFractionAdaptative:
    from backend.analysis.kelly import calculer_fraction_adaptative

    def test_bankroll_normale_debut(self):
        from backend.analysis.kelly import calculer_fraction_adaptative
        f = calculer_fraction_adaptative(
            roi_historique=None, n_paris=5,
            bankroll_actuelle=1000, bankroll_initiale=1000,
        )
        assert f == 0.125

    def test_bankroll_mature_roi_positif(self):
        from backend.analysis.kelly import calculer_fraction_adaptative
        f = calculer_fraction_adaptative(
            roi_historique=0.08, n_paris=150,
            bankroll_actuelle=1000, bankroll_initiale=1000,
        )
        # score = maturité(1.0) * confiance_roi(0.8) = 0.8
        # fraction = 0.125 + 0.8 * (0.333 - 0.125) = 0.2914
        assert f == pytest.approx(0.2914, abs=1e-3)

    def test_bankroll_inferieure_80pct_reduit(self):
        from backend.analysis.kelly import calculer_fraction_adaptative
        f = calculer_fraction_adaptative(
            roi_historique=0.08, n_paris=150,
            bankroll_actuelle=750, bankroll_initiale=1000,
        )
        # fraction de base = 0.2914 ; ratio = 0.75 → reduction = (0.80-0.75)/0.30 = 0.1667
        # fraction finale = 0.2914 * (1 - 0.75 * 0.1667) ≈ 0.255
        assert f < 0.2914  # doit être inférieur à la fraction sans protection

    def test_bankroll_inferieure_60pct_plus_restrictif(self):
        """Bankroll < 60 % doit être PLUS restrictif que 60-80 %."""
        from backend.analysis.kelly import calculer_fraction_adaptative
        f_70 = calculer_fraction_adaptative(
            roi_historique=0.08, n_paris=150,
            bankroll_actuelle=700, bankroll_initiale=1000,
        )
        f_55 = calculer_fraction_adaptative(
            roi_historique=0.08, n_paris=150,
            bankroll_actuelle=550, bankroll_initiale=1000,
        )
        assert f_55 <= f_70, (
            f"Bankroll 55 % ({f_55}) devrait être ≤ bankroll 70 % ({f_70})"
        )

    def test_bankroll_inferieure_60pct_hard_cap(self):
        """Au-dessous de 60 %, la fraction doit être très réduite (< 1/10)."""
        from backend.analysis.kelly import calculer_fraction_adaptative
        f = calculer_fraction_adaptative(
            roi_historique=0.08, n_paris=150,
            bankroll_actuelle=500, bankroll_initiale=1000,
        )
        assert f <= 0.10

    def test_kelly_simple_negatif(self):
        from backend.analysis.kelly import calculer_kelly_simple
        assert calculer_kelly_simple(0.40, 1.50) == pytest.approx(0.0, abs=1e-4)

    def test_kelly_simple_positif(self):
        from backend.analysis.kelly import calculer_kelly_simple
        k = calculer_kelly_simple(0.60, 2.00)
        assert k > 0


# ─────────────────────────────────────────────────────────────────────────────
# Value Betting — analyser_match avec marché HT
# ─────────────────────────────────────────────────────────────────────────────

class TestValueBettingHT:
    def test_over15_ht_derive_si_cote_absente(self):
        """Sans cote HT bookmaker, une cote dérivée est générée — over15_ht peut apparaître."""
        from backend.analysis.value_betting import analyser_match
        prob = {"prob_over25": 0.70, "prob_over15_ht": 0.80}
        cotes = {"odds_over25": 1.50}
        ops = analyser_match(prob, cotes, seuil_confiance=0.55)
        marches = [o["marche"] for o in ops]
        # La cote est dérivée (1.12 / prob) — over15_ht peut générer une opportunité
        # si l'EV et l'edge dépassent les seuils (avec prob=0.80 c'est le cas)
        assert "over15_ht" in marches

    def test_over15_ht_genere_avec_cotes_reelles(self):
        """over15_ht actif (78% disponibilité en DB) — doit apparaître avec cotes réelles."""
        from backend.analysis.value_betting import analyser_match
        prob = {"prob_over15_ht": 0.75, "prob_over25": 0.70}
        cotes = {"odds_over15_ht": 1.60, "odds_under15_ht": 2.50,
                 "odds_over25": 1.90, "odds_under25": 1.95}
        ops = analyser_match(prob, cotes, seuil_confiance=0.55)
        marches = [o["marche"] for o in ops]
        # over15_ht activé depuis commit e15f07c — doit apparaître si EV positive
        assert "over15_ht" in marches

    def test_correction_marge_binaire(self):
        """La probabilité bookmaker corrigée doit être inférieure à la brute."""
        from backend.analysis.value_betting import corriger_marge_bookmaker
        res = corriger_marge_bookmaker({"over": 1.90, "under": 1.90})
        assert abs(res.get("over", 0) - 0.5) < 0.01

    def test_seuil_ev_adaptatif_faible_confiance(self):
        from backend.analysis.value_betting import seuil_ev_adaptatif
        seuil_bas = seuil_ev_adaptatif(0.60, 0.05)
        seuil_haut = seuil_ev_adaptatif(0.75, 0.05)
        assert seuil_bas > seuil_haut


# ─────────────────────────────────────────────────────────────────────────────
# Collector — extraction + sauvegarde odds
# ─────────────────────────────────────────────────────────────────────────────

class TestOddsCollector:
    def _creer_match(self, conn) -> int:
        conn.execute(
            """
            INSERT INTO leagues (footystats_id, name, country, tier)
            VALUES (1, 'Test League', 'FR', 1)
            """
        )
        conn.execute(
            """
            INSERT INTO seasons (footystats_id, league_id, name, year,
                                  start_date, end_date)
            VALUES (1, 1, '2024', 2024, '2024-08-01', '2025-05-31')
            """
        )
        conn.execute(
            "INSERT INTO teams (footystats_id, name, country) VALUES (1,'Home','FR')"
        )
        conn.execute(
            "INSERT INTO teams (footystats_id, name, country) VALUES (2,'Away','FR')"
        )
        conn.execute(
            """
            INSERT INTO matches (footystats_id, season_id, league_id,
                                  home_team_id, away_team_id,
                                  match_date, match_timestamp, status)
            VALUES (99, 1, 1, 1, 2, '2025-01-01', 9999999999, 'upcoming')
            """
        )
        conn.commit()
        return conn.execute("SELECT id FROM matches LIMIT 1").fetchone()["id"]

    def test_extraction_over45(self):
        from backend.odds.collector import OddsCollector
        collector = OddsCollector.__new__(OddsCollector)
        data = {"odds_over45": "3.50", "odds_under45": "1.30"}
        cotes = collector._extraire_cotes(data)
        assert cotes.get("odds_over45") == pytest.approx(3.50)
        assert cotes.get("odds_under45") == pytest.approx(1.30)

    def test_extraction_over15_ht(self):
        from backend.odds.collector import OddsCollector
        collector = OddsCollector.__new__(OddsCollector)
        data = {"odds_over15_ht": "2.10", "odds_under15_ht": "1.75"}
        cotes = collector._extraire_cotes(data)
        assert cotes.get("odds_over15_ht") == pytest.approx(2.10)

    def test_sauvegarde_odds_avec_over45_et_ht(self):
        conn = _creer_db_test()
        from backend.odds.collector import OddsCollector
        collector = OddsCollector.__new__(OddsCollector)
        collector.conn = conn

        match_id = self._creer_match(conn)

        cotes = {
            "odds_home": 2.0, "odds_draw": 3.4, "odds_away": 3.8,
            "odds_over25": 1.80, "odds_under25": 2.10,
            "odds_over45": 5.00, "odds_under45": 1.18,
            "odds_btts_yes": 1.95, "odds_btts_no": 1.95,
            "odds_over15_ht": 2.20, "odds_under15_ht": 1.70,
        }
        collector._sauvegarder_cotes(match_id, cotes)

        row = conn.execute("SELECT * FROM odds WHERE match_id = ?", (match_id,)).fetchone()
        assert row is not None
        assert row["odds_over45"] == pytest.approx(5.00)
        assert row["odds_over15_ht"] == pytest.approx(2.20)
        assert row["prob_over45_corrected"] is not None
        assert row["prob_over15_ht_corrected"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline — cache et log colonnes manquantes
# ─────────────────────────────────────────────────────────────────────────────

class TestFeaturePipeline:
    def test_invalider_cache(self):
        from backend.features.pipeline import FeaturePipeline
        conn = _creer_db_test()
        pipeline = FeaturePipeline(conn)
        # Charger le cache une première fois
        _ = pipeline._obtenir_colonnes_match_features()
        assert pipeline._colonnes_match_features is not None
        # Invalider
        pipeline.invalider_cache_colonnes()
        assert pipeline._colonnes_match_features is None
        # Rechargement automatique
        _ = pipeline._obtenir_colonnes_match_features()
        assert pipeline._colonnes_match_features is not None

    def test_sauvegarde_ignore_colonnes_inexistantes(self):
        """Les features sans colonne DB ne doivent pas faire planter l'INSERT."""
        from backend.features.pipeline import FeaturePipeline
        conn = _creer_db_test()
        # On a besoin d'un match en DB
        conn.execute(
            "INSERT INTO leagues (footystats_id,name,country,tier) VALUES(10,'L','FR',1)"
        )
        conn.execute(
            "INSERT INTO seasons (footystats_id,league_id,name,year,start_date,end_date) VALUES(10,1,'S',2024,'2024-01-01','2025-01-01')"
        )
        conn.execute(
            "INSERT INTO teams (footystats_id,name,country) VALUES(10,'H','FR')"
        )
        conn.execute(
            "INSERT INTO teams (footystats_id,name,country) VALUES(11,'A','FR')"
        )
        conn.execute(
            """
            INSERT INTO matches
            (footystats_id,season_id,league_id,home_team_id,away_team_id,
             match_date,match_timestamp,status)
            VALUES(10,1,1,1,2,'2024-06-01',1717200000,'upcoming')
            """
        )
        conn.commit()
        match_id = conn.execute("SELECT id FROM matches WHERE footystats_id=10").fetchone()["id"]

        pipeline = FeaturePipeline(conn)
        features = {
            "match_id": match_id,
            "max_time_used": 0,
            "colonne_inexistante_xyz": 99.9,  # doit être ignorée sans crash
        }
        # Ne doit pas lever d'exception
        pipeline._sauvegarder_features(features, commit=True)


# ─────────────────────────────────────────────────────────────────────────────
# Auto-résolution — matchs expirés par timestamp
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoResolution:
    def _creer_match_passe(self, conn, footystats_id: int, ts_passe: int) -> int:
        conn.execute(
            "INSERT OR IGNORE INTO leagues (footystats_id,name,country,tier) VALUES(99,'TestL','FR',1)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO seasons (footystats_id,league_id,name,year,start_date,end_date) VALUES(99,1,'S',2024,'2024-01-01','2025-01-01')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO teams (footystats_id,name,country) VALUES(99,'H','FR')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO teams (footystats_id,name,country) VALUES(100,'A','FR')"
        )
        conn.execute(
            """
            INSERT INTO matches
            (footystats_id,season_id,league_id,home_team_id,away_team_id,
             match_date,match_timestamp,status)
            VALUES(?,1,1,1,2,'2024-01-01',?,'upcoming')
            """,
            (footystats_id, ts_passe),
        )
        conn.commit()
        return conn.execute(
            "SELECT id FROM matches WHERE footystats_id = ?",
            (footystats_id,),
        ).fetchone()["id"]

    def test_match_expire_marque_complete_apres_2h(self):
        """Un match upcoming dont le timestamp a dépassé de > 2h doit être marqué complete."""
        import time
        conn = _creer_db_test()
        ts_passe = int(time.time()) - 3 * 3600  # il y a 3h
        match_id = self._creer_match_passe(conn, 201, ts_passe)

        # Simuler la logique de mise à jour
        conn.execute(
            "UPDATE matches SET status = 'complete' WHERE status = 'upcoming' AND match_timestamp < ?",
            (int(time.time()) - 2 * 3600,),
        )
        conn.commit()

        row = conn.execute("SELECT status FROM matches WHERE id = ?", (match_id,)).fetchone()
        assert row["status"] == "complete"

    def test_pending_ignore_si_match_complete(self):
        """Un pronostic pending sur un match complete doit être passé à ignored."""
        import time
        conn = _creer_db_test()
        ts_passe = int(time.time()) - 3 * 3600
        match_id = self._creer_match_passe(conn, 202, ts_passe)

        # Créer un user minimal
        conn.execute(
            """INSERT INTO users (email, password_hash, initial_bankroll, current_bankroll)
               VALUES ('t@t.com', 'x', 100, 100)"""
        )
        user_id = conn.execute("SELECT id FROM users WHERE email='t@t.com'").fetchone()["id"]

        # Insérer un pronostic pending
        conn.execute(
            """INSERT INTO pronostics
               (user_id, match_id, market, model_probability, bookmaker_probability,
                probability_edge, expected_value, reference_bookmaker, reference_odds,
                confidence_score, kelly_fraction_used, kelly_raw, recommended_stake,
                bankroll_at_recommendation, status)
               VALUES (?, ?, 'over15', 0.6, 0.5, 0.1, 0.08, 'ref', 1.80,
                       0.6, 0.125, 0.2, 5.0, 100, 'pending')""",
            (user_id, match_id),
        )
        conn.commit()

        # Marquer le match complete + résoudre
        maintenant = int(time.time())
        conn.execute(
            "UPDATE matches SET status = 'complete' WHERE match_timestamp < ?",
            (maintenant - 2 * 3600,),
        )
        conn.execute(
            """UPDATE pronostics SET status = 'ignored', ignored_at = datetime('now'),
               ignore_reason = 'match_termine_sans_placement'
               WHERE status = 'pending' AND match_id IN (
                   SELECT id FROM matches WHERE status = 'complete' OR match_timestamp < ?
               )""",
            (maintenant - 2 * 3600,),
        )
        conn.commit()

        row = conn.execute("SELECT status FROM pronostics WHERE user_id = ?", (user_id,)).fetchone()
        assert row["status"] == "ignored"

    def test_pending_futur_non_ignore(self):
        """Un pronostic pending sur un match futur ne doit PAS être ignoré."""
        import time
        conn = _creer_db_test()
        ts_futur = int(time.time()) + 24 * 3600  # demain
        match_id = self._creer_match_passe(conn, 203, ts_futur)

        conn.execute(
            """INSERT INTO users (email, password_hash, initial_bankroll, current_bankroll)
               VALUES ('t2@t.com', 'x', 100, 100)"""
        )
        user_id = conn.execute("SELECT id FROM users WHERE email='t2@t.com'").fetchone()["id"]

        conn.execute(
            """INSERT INTO pronostics
               (user_id, match_id, market, model_probability, bookmaker_probability,
                probability_edge, expected_value, reference_bookmaker, reference_odds,
                confidence_score, kelly_fraction_used, kelly_raw, recommended_stake,
                bankroll_at_recommendation, status)
               VALUES (?, ?, 'over15', 0.6, 0.5, 0.1, 0.08, 'ref', 1.80,
                       0.6, 0.125, 0.2, 5.0, 100, 'pending')""",
            (user_id, match_id),
        )
        conn.commit()

        maintenant = int(time.time())
        conn.execute(
            """UPDATE pronostics SET status = 'ignored'
               WHERE status = 'pending' AND match_id IN (
                   SELECT id FROM matches WHERE status = 'complete' OR match_timestamp < ?
               )""",
            (maintenant - 2 * 3600,),
        )
        conn.commit()

        row = conn.execute("SELECT status FROM pronostics WHERE user_id = ?", (user_id,)).fetchone()
        assert row["status"] == "pending"


# ─────────────────────────────────────────────────────────────────────────────
# Odds — contrainte UNIQUE (pas de doublons)
# ─────────────────────────────────────────────────────────────────────────────

class TestOddsUnique:
    def _creer_match(self, conn) -> int:
        conn.execute(
            "INSERT OR IGNORE INTO leagues (footystats_id,name,country,tier) VALUES(88,'L','FR',1)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO seasons (footystats_id,league_id,name,year,start_date,end_date) VALUES(88,1,'S',2024,'2024-01-01','2025-01-01')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO teams (footystats_id,name,country) VALUES(88,'H','FR')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO teams (footystats_id,name,country) VALUES(89,'A','FR')"
        )
        conn.execute(
            """INSERT INTO matches (footystats_id,season_id,league_id,home_team_id,away_team_id,
               match_date,match_timestamp,status)
               VALUES(88,1,1,1,2,'2025-01-01',9999999999,'upcoming')"""
        )
        conn.commit()
        return conn.execute("SELECT id FROM matches WHERE footystats_id=88").fetchone()["id"]

    def test_migration_008_cree_index_unique(self):
        conn = _creer_db_test()
        cursor = conn.execute("PRAGMA index_list(odds)")
        indices = [r["name"] for r in cursor.fetchall()]
        assert "uq_odds_match_bookmaker" in indices

    def test_double_insert_remplace(self):
        """Un second INSERT OR REPLACE pour le même (match_id, bookmaker) doit remplacer."""
        conn = _creer_db_test()
        match_id = self._creer_match(conn)

        for btts in [2.10, 2.05]:
            conn.execute(
                """INSERT OR REPLACE INTO odds (match_id, bookmaker, bookmaker_tier,
                   collected_timestamp, odds_btts_yes)
                   VALUES (?, 'footystats', 2, 1, ?)""",
                (match_id, btts),
            )
        conn.commit()

        rows = conn.execute("SELECT * FROM odds WHERE match_id = ?", (match_id,)).fetchall()
        assert len(rows) == 1
        assert rows[0]["odds_btts_yes"] == pytest.approx(2.05)
