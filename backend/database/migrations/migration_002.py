"""
Migration 002 — Tables ML et performance.
Crée les tables pour les prédictions,
features, modèles et snapshots de performance.
"""

import sqlite3

DESCRIPTION = "Tables ML, prédictions et performance"


def appliquer(conn: sqlite3.Connection) -> None:
    """
    Crée les tables ML et de performance.
    """

    # Table des versions de modèles
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_versions (
            id                          INTEGER PRIMARY KEY,
            version                     TEXT NOT NULL UNIQUE,
            trained_at                  TEXT NOT NULL,
            training_data_start         TEXT NOT NULL,
            training_data_end           TEXT NOT NULL,
            total_matches_trained       INTEGER NOT NULL DEFAULT 0,
            brier_score_over25          REAL,
            brier_score_btts            REAL,
            brier_score_1x2             REAL,
            log_loss_over25             REAL,
            log_loss_btts               REAL,
            log_loss_1x2                REAL,
            auc_roc_over25              REAL,
            auc_roc_btts                REAL,
            auc_roc_1x2                 REAL,
            simulated_roi               REAL,
            hyperparameters_json        TEXT,
            selected_features_json      TEXT,
            artifact_path               TEXT,
            is_active                   INTEGER DEFAULT 0,
            notes                       TEXT,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_versions_is_active
        ON model_versions(is_active)
    """)

    # Table des prédictions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id                          INTEGER PRIMARY KEY,
            match_id                    INTEGER NOT NULL UNIQUE,
            model_version               TEXT NOT NULL DEFAULT 'initial',
            predicted_at                TEXT NOT NULL DEFAULT (datetime('now')),
            dc_prob_home_win            REAL,
            dc_prob_draw                REAL,
            dc_prob_away_win            REAL,
            dc_lambda                   REAL,
            dc_mu                       REAL,
            ml_prob_over15              REAL,
            ml_prob_over25              REAL,
            ml_prob_over35              REAL,
            ml_prob_over45              REAL,
            ml_prob_btts                REAL,
            ml_prob_home_win            REAL,
            ml_prob_draw                REAL,
            ml_prob_away_win            REAL,
            prob_home_win               REAL NOT NULL DEFAULT 0.33,
            prob_draw                   REAL NOT NULL DEFAULT 0.33,
            prob_away_win               REAL NOT NULL DEFAULT 0.33,
            prob_over15                 REAL NOT NULL DEFAULT 0.5,
            prob_over25                 REAL NOT NULL DEFAULT 0.5,
            prob_over35                 REAL NOT NULL DEFAULT 0.5,
            prob_over45                 REAL NOT NULL DEFAULT 0.5,
            prob_btts                   REAL NOT NULL DEFAULT 0.5,
            prob_btts_no                REAL NOT NULL DEFAULT 0.5,
            prob_gg_over25              REAL,
            prob_gg_under25             REAL,
            prob_ht_home_win            REAL,
            prob_ht_draw                REAL,
            prob_ht_away_win            REAL,
            prob_ht_btts                REAL,
            score_matrix_json           TEXT,
            most_likely_score           TEXT,
            most_likely_score_prob      REAL,
            uncertainty_score           REAL,
            context_modifiers_json      TEXT,
            model_confidence            REAL,
            FOREIGN KEY (match_id) REFERENCES matches(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_match_id
        ON predictions(match_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_predicted_at
        ON predictions(predicted_at)
    """)

    # Table des features
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_features (
            id                              INTEGER PRIMARY KEY,
            match_id                        INTEGER NOT NULL UNIQUE,
            calculated_at                   TEXT NOT NULL DEFAULT (datetime('now')),
            max_time_used                   INTEGER NOT NULL DEFAULT 0,
            home_goals_scored_3m            REAL,
            home_goals_scored_5m            REAL,
            home_goals_scored_10m           REAL,
            home_goals_scored_20m           REAL,
            home_goals_conceded_3m          REAL,
            home_goals_conceded_5m          REAL,
            home_goals_conceded_10m         REAL,
            home_goals_conceded_20m         REAL,
            home_over25_rate_5m             REAL,
            home_over25_rate_10m            REAL,
            home_btts_rate_5m               REAL,
            home_btts_rate_10m              REAL,
            home_clean_sheet_rate_10m       REAL,
            home_xg_generated_5m            REAL,
            home_xg_conceded_5m             REAL,
            home_xg_diff_5m                 REAL,
            home_ppm_5m                     REAL,
            home_ppm_10m                    REAL,
            home_win_streak                 INTEGER,
            home_momentum_score             REAL,
            home_rest_days                  INTEGER,
            home_matches_last_14            INTEGER,
            away_goals_scored_3m            REAL,
            away_goals_scored_5m            REAL,
            away_goals_scored_10m           REAL,
            away_goals_scored_20m           REAL,
            away_goals_conceded_3m          REAL,
            away_goals_conceded_5m          REAL,
            away_goals_conceded_10m         REAL,
            away_goals_conceded_20m         REAL,
            away_over25_rate_5m             REAL,
            away_over25_rate_10m            REAL,
            away_btts_rate_5m               REAL,
            away_btts_rate_10m              REAL,
            away_clean_sheet_rate_10m       REAL,
            away_xg_generated_5m            REAL,
            away_xg_conceded_5m             REAL,
            away_xg_diff_5m                 REAL,
            away_ppm_5m                     REAL,
            away_ppm_10m                    REAL,
            away_win_streak                 INTEGER,
            away_momentum_score             REAL,
            away_rest_days                  INTEGER,
            away_matches_last_14            INTEGER,
            h2h_home_wins_5                 INTEGER,
            h2h_draws_5                     INTEGER,
            h2h_away_wins_5                 INTEGER,
            h2h_goals_avg_5                 REAL,
            h2h_btts_rate_5                 REAL,
            h2h_over25_rate_5               REAL,
            h2h_dominance_score             REAL,
            home_position_normalized        REAL,
            home_points_gap_leader          INTEGER,
            home_points_gap_relegation      INTEGER,
            away_position_normalized        REAL,
            away_points_gap_leader          INTEGER,
            away_points_gap_relegation      INTEGER,
            points_gap_between_teams        INTEGER,
            league_goals_avg                REAL,
            league_btts_rate                REAL,
            league_over25_rate              REAL,
            league_volatility               REAL,
            match_importance_score          REAL,
            game_week_normalized            REAL,
            competition_type_encoded        INTEGER,
            is_derby                        INTEGER,
            dc_lambda                       REAL,
            dc_mu                           REAL,
            dc_rho                          REAL,
            FOREIGN KEY (match_id) REFERENCES matches(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_match_features_match_id
        ON match_features(match_id)
    """)

    # Table des explications SHAP
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shap_explanations (
            id                          INTEGER PRIMARY KEY,
            prediction_id               INTEGER NOT NULL,
            market                      TEXT NOT NULL,
            top_features_json           TEXT NOT NULL,
            base_value                  REAL,
            final_value                 REAL,
            calculated_at               TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (prediction_id) REFERENCES predictions(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_shap_prediction_id
        ON shap_explanations(prediction_id)
    """)

    # Table des snapshots de performance
    conn.execute("""
        CREATE TABLE IF NOT EXISTS performance_snapshots (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            snapshot_date               TEXT NOT NULL,
            snapshot_type               TEXT NOT NULL,
            bankroll_start              REAL NOT NULL,
            bankroll_end                REAL NOT NULL,
            bankroll_change             REAL NOT NULL DEFAULT 0,
            bankroll_change_pct         REAL NOT NULL DEFAULT 0,
            total_bets                  INTEGER NOT NULL DEFAULT 0,
            bets_won                    INTEGER NOT NULL DEFAULT 0,
            bets_lost                   INTEGER NOT NULL DEFAULT 0,
            bets_void                   INTEGER NOT NULL DEFAULT 0,
            bets_ignored                INTEGER NOT NULL DEFAULT 0,
            win_rate                    REAL,
            total_staked                REAL NOT NULL DEFAULT 0,
            total_returns               REAL NOT NULL DEFAULT 0,
            total_profit                REAL NOT NULL DEFAULT 0,
            roi                         REAL,
            yield                       REAL,
            avg_clv                     REAL,
            positive_clv_rate           REAL,
            max_drawdown_period         REAL,
            current_drawdown            REAL,
            performance_by_market_json  TEXT,
            performance_by_league_json  TEXT,
            brier_score_period          REAL,
            avg_confidence_score        REAL,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (user_id, snapshot_date, snapshot_type)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_snapshots_user_id
        ON performance_snapshots(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_snapshots_date
        ON performance_snapshots(snapshot_date)
    """)

    # Table des notifications
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications_log (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            device_id                   INTEGER,
            category                    TEXT NOT NULL,
            subcategory                 TEXT NOT NULL,
            title                       TEXT NOT NULL,
            body                        TEXT NOT NULL,
            data_json                   TEXT,
            status                      TEXT NOT NULL DEFAULT 'pending',
            ttl_seconds                 INTEGER DEFAULT 86400,
            sent_at                     TEXT,
            opened_at                   TEXT,
            error_message               TEXT,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (device_id) REFERENCES user_devices(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_notif_log_user_id
        ON notifications_log(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_notif_log_status
        ON notifications_log(status)
    """)

    # Table des combinés
    conn.execute("""
        CREATE TABLE IF NOT EXISTS combines (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            combined_probability        REAL NOT NULL,
            combined_odds               REAL NOT NULL,
            combined_ev                 REAL NOT NULL,
            correlation_max             REAL NOT NULL,
            kelly_fraction_used         REAL NOT NULL,
            kelly_raw                   REAL NOT NULL,
            recommended_stake           REAL NOT NULL,
            bankroll_at_recommendation  REAL NOT NULL,
            status                      TEXT NOT NULL DEFAULT 'pending',
            actual_stake                REAL,
            actual_profit               REAL,
            recommended_at              TEXT NOT NULL DEFAULT (datetime('now')),
            placed_at                   TEXT,
            resolved_at                 TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
