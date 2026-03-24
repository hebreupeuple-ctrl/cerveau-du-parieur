"""
Migration 001 — Schéma initial.
Crée toutes les tables de données brutes et utilisateur.
"""

import sqlite3

DESCRIPTION = "Schéma initial — tables de base"


def appliquer(conn: sqlite3.Connection) -> None:
    """
    Crée toutes les tables du système.
    """

    # Table des ligues
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leagues (
            id                      INTEGER PRIMARY KEY,
            footystats_id           INTEGER UNIQUE NOT NULL,
            name                    TEXT NOT NULL,
            country                 TEXT NOT NULL,
            tier                    INTEGER NOT NULL DEFAULT 1,
            group_type              TEXT NOT NULL DEFAULT 'major_european',
            season_start_month      INTEGER NOT NULL DEFAULT 8,
            season_end_month        INTEGER NOT NULL DEFAULT 5,
            avg_goals_per_match     REAL,
            avg_btts_rate           REAL,
            avg_over25_rate         REAL,
            home_advantage_factor   REAL DEFAULT 1.15,
            is_active               INTEGER NOT NULL DEFAULT 1,
            priority                INTEGER NOT NULL DEFAULT 1,
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_leagues_footystats_id
        ON leagues(footystats_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_leagues_is_active
        ON leagues(is_active)
    """)

    # Table des saisons
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            id                      INTEGER PRIMARY KEY,
            footystats_id           INTEGER UNIQUE NOT NULL,
            league_id               INTEGER NOT NULL,
            name                    TEXT NOT NULL,
            year                    INTEGER NOT NULL,
            start_date              TEXT NOT NULL,
            end_date                TEXT NOT NULL,
            total_rounds            INTEGER,
            current_round           INTEGER DEFAULT 0,
            status                  TEXT NOT NULL DEFAULT 'upcoming',
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (league_id) REFERENCES leagues(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_seasons_league_id
        ON seasons(league_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_seasons_status
        ON seasons(status)
    """)

    # Table des équipes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id                          INTEGER PRIMARY KEY,
            footystats_id               INTEGER UNIQUE NOT NULL,
            name                        TEXT NOT NULL,
            country                     TEXT NOT NULL,
            founded_year                INTEGER,
            attack_strength_home        REAL DEFAULT 1.0,
            attack_strength_away        REAL DEFAULT 1.0,
            defense_strength_home       REAL DEFAULT 1.0,
            defense_strength_away       REAL DEFAULT 1.0,
            kalman_variance_attack      REAL DEFAULT 0.1,
            kalman_variance_defense     REAL DEFAULT 0.1,
            tactical_profile            TEXT DEFAULT 'balanced',
            is_promoted                 INTEGER DEFAULT 0,
            promotion_season_id         INTEGER,
            promotion_factor_attack     REAL DEFAULT 0.77,
            promotion_factor_defense    REAL DEFAULT 0.69,
            matches_since_promotion     INTEGER DEFAULT 0,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_teams_footystats_id
        ON teams(footystats_id)
    """)

    # Table des arbitres
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referees (
            id                      INTEGER PRIMARY KEY,
            footystats_id           INTEGER UNIQUE,
            name                    TEXT NOT NULL,
            country                 TEXT,
            avg_yellow_cards        REAL DEFAULT 0.0,
            avg_red_cards           REAL DEFAULT 0.0,
            avg_penalties           REAL DEFAULT 0.0,
            avg_goals_per_match     REAL DEFAULT 0.0,
            home_bias_score         REAL DEFAULT 0.0,
            goals_impact            REAL DEFAULT 0.0,
            matches_officiated      INTEGER DEFAULT 0,
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Table des matchs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id                          INTEGER PRIMARY KEY,
            footystats_id               INTEGER UNIQUE NOT NULL,
            season_id                   INTEGER NOT NULL,
            league_id                   INTEGER NOT NULL,
            home_team_id                INTEGER NOT NULL,
            away_team_id                INTEGER NOT NULL,
            referee_id                  INTEGER,
            match_date                  TEXT NOT NULL,
            match_timestamp             INTEGER NOT NULL,
            game_week                   INTEGER,
            kickoff_time                TEXT,
            status                      TEXT NOT NULL DEFAULT 'upcoming',
            home_goals                  INTEGER,
            away_goals                  INTEGER,
            home_goals_ht               INTEGER,
            away_goals_ht               INTEGER,
            total_goals                 INTEGER,
            result_1x2                  TEXT,
            over15                      INTEGER,
            over25                      INTEGER,
            over35                      INTEGER,
            over45                      INTEGER,
            btts                        INTEGER,
            btts_ht                     INTEGER,
            home_shots                  INTEGER,
            away_shots                  INTEGER,
            home_shots_on_target        INTEGER,
            away_shots_on_target        INTEGER,
            home_corners                INTEGER,
            away_corners                INTEGER,
            home_yellow_cards           INTEGER,
            away_yellow_cards           INTEGER,
            home_red_cards              INTEGER,
            away_red_cards              INTEGER,
            home_possession             REAL,
            away_possession             REAL,
            home_xg                     REAL,
            away_xg                     REAL,
            home_offsides               INTEGER,
            away_offsides               INTEGER,
            home_rest_days              INTEGER,
            away_rest_days              INTEGER,
            home_matches_last_14_days   INTEGER,
            away_matches_last_14_days   INTEGER,
            match_importance_score      REAL DEFAULT 0.0,
            is_derby                    INTEGER DEFAULT 0,
            competition_type            TEXT DEFAULT 'league',
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (season_id) REFERENCES seasons(id),
            FOREIGN KEY (league_id) REFERENCES leagues(id),
            FOREIGN KEY (home_team_id) REFERENCES teams(id),
            FOREIGN KEY (away_team_id) REFERENCES teams(id),
            FOREIGN KEY (referee_id) REFERENCES referees(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_footystats_id
        ON matches(footystats_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_season_id
        ON matches(season_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_league_id
        ON matches(league_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_home_team_id
        ON matches(home_team_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_away_team_id
        ON matches(away_team_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_match_timestamp
        ON matches(match_timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_status
        ON matches(status)
    """)

    # Table des cotes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS odds (
            id                          INTEGER PRIMARY KEY,
            match_id                    INTEGER NOT NULL,
            bookmaker                   TEXT NOT NULL,
            bookmaker_tier              INTEGER NOT NULL DEFAULT 3,
            collected_at                TEXT NOT NULL DEFAULT (datetime('now')),
            collected_timestamp         INTEGER NOT NULL,
            hours_before_kickoff        REAL,
            odds_home                   REAL,
            odds_draw                   REAL,
            odds_away                   REAL,
            prob_home_corrected         REAL,
            prob_draw_corrected         REAL,
            prob_away_corrected         REAL,
            bookmaker_margin            REAL,
            odds_over15                 REAL,
            odds_under15                REAL,
            odds_over25                 REAL,
            odds_under25                REAL,
            odds_over35                 REAL,
            odds_under35                REAL,
            odds_over45                 REAL,
            odds_under45                REAL,
            prob_over15_corrected       REAL,
            prob_over25_corrected       REAL,
            prob_over35_corrected       REAL,
            prob_over45_corrected       REAL,
            odds_btts_yes               REAL,
            odds_btts_no                REAL,
            prob_btts_corrected         REAL,
            movement_home               REAL DEFAULT 0.0,
            movement_draw               REAL DEFAULT 0.0,
            movement_away               REAL DEFAULT 0.0,
            movement_over25             REAL DEFAULT 0.0,
            movement_btts               REAL DEFAULT 0.0,
            movement_type               TEXT,
            is_opening                  INTEGER DEFAULT 0,
            is_closing                  INTEGER DEFAULT 0,
            FOREIGN KEY (match_id) REFERENCES matches(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_match_id
        ON odds(match_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_bookmaker_tier
        ON odds(bookmaker_tier)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_is_closing
        ON odds(is_closing)
    """)

    # Table des utilisateurs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                          INTEGER PRIMARY KEY,
            email                       TEXT NOT NULL UNIQUE,
            password_hash               TEXT NOT NULL,
            initial_bankroll            REAL NOT NULL,
            current_bankroll            REAL NOT NULL,
            bankroll_updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
            kelly_fraction              REAL NOT NULL DEFAULT 0.125,
            min_confidence_simple       REAL NOT NULL DEFAULT 0.60,
            min_confidence_combine      REAL NOT NULL DEFAULT 0.65,
            min_ev_threshold            REAL NOT NULL DEFAULT 0.03,
            min_prob_edge               REAL NOT NULL DEFAULT 0.05,
            urgency_threshold           REAL NOT NULL DEFAULT 0.85,
            timezone                    TEXT NOT NULL DEFAULT 'UTC',
            is_active                   INTEGER NOT NULL DEFAULT 1,
            onboarding_completed        INTEGER NOT NULL DEFAULT 0,
            system_mode                 TEXT NOT NULL DEFAULT 'active',
            failed_login_attempts       INTEGER NOT NULL DEFAULT 0,
            locked_until                TEXT,
            last_login_at               TEXT,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_email
        ON users(email)
    """)

    # Table des appareils
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_devices (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            device_fingerprint          TEXT NOT NULL,
            device_name                 TEXT,
            platform                    TEXT,
            push_subscription_json      TEXT,
            is_authorized               INTEGER NOT NULL DEFAULT 0,
            authorized_at               TEXT,
            last_seen_at                TEXT,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            UNIQUE (user_id, device_fingerprint)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_devices_user_id
        ON user_devices(user_id)
    """)

    # Table des tokens JWT
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_tokens (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            token_hash                  TEXT NOT NULL UNIQUE,
            device_id                   INTEGER,
            expires_at                  TEXT NOT NULL,
            is_revoked                  INTEGER NOT NULL DEFAULT 0,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES user_devices(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_tokens_token_hash
        ON user_tokens(token_hash)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_tokens_expires_at
        ON user_tokens(expires_at)
    """)

    # Table des marchés utilisateur
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_markets (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            market                      TEXT NOT NULL,
            is_active                   INTEGER NOT NULL DEFAULT 1,
            auto_disabled               INTEGER NOT NULL DEFAULT 0,
            disable_reason              TEXT,
            disabled_at                 TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            UNIQUE (user_id, market)
        )
    """)

    # Table des ligues utilisateur
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_leagues (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            league_id                   INTEGER NOT NULL,
            is_active                   INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            FOREIGN KEY (league_id) REFERENCES leagues(id),
            UNIQUE (user_id, league_id)
        )
    """)

    # Table des pronostics
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pronostics (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            match_id                    INTEGER NOT NULL,
            prediction_id               INTEGER,
            market                      TEXT NOT NULL,
            model_probability           REAL NOT NULL,
            bookmaker_probability       REAL NOT NULL,
            probability_edge            REAL NOT NULL,
            expected_value              REAL NOT NULL,
            reference_bookmaker         TEXT NOT NULL,
            reference_odds              REAL NOT NULL,
            movement_type               TEXT,
            confidence_score            REAL NOT NULL,
            kelly_fraction_used         REAL NOT NULL,
            kelly_raw                   REAL NOT NULL,
            recommended_stake           REAL NOT NULL,
            bankroll_at_recommendation  REAL NOT NULL,
            is_part_of_combine          INTEGER NOT NULL DEFAULT 0,
            combine_id                  INTEGER,
            status                      TEXT NOT NULL DEFAULT 'pending',
            actual_stake                REAL,
            actual_odds                 REAL,
            actual_profit               REAL,
            closing_odds                REAL,
            clv                         REAL,
            recommended_at              TEXT NOT NULL DEFAULT (datetime('now')),
            placed_at                   TEXT,
            ignored_at                  TEXT,
            resolved_at                 TEXT,
            ignore_reason               TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pronostics_user_id
        ON pronostics(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pronostics_status
        ON pronostics(status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pronostics_match_id
        ON pronostics(match_id)
    """)

    # Table des logs système
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id                          INTEGER PRIMARY KEY,
            level                       TEXT NOT NULL,
            module                      TEXT NOT NULL,
            message                     TEXT NOT NULL,
            details_json                TEXT,
            task_name                   TEXT,
            execution_time_ms           INTEGER,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_system_logs_level
        ON system_logs(level)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_system_logs_created_at
        ON system_logs(created_at)
    """)

    # Table des jobs scheduler
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_jobs (
            id                          INTEGER PRIMARY KEY,
            job_name                    TEXT NOT NULL,
            started_at                  TEXT NOT NULL,
            completed_at                TEXT,
            status                      TEXT NOT NULL DEFAULT 'running',
            attempt_number              INTEGER NOT NULL DEFAULT 1,
            max_attempts                INTEGER NOT NULL DEFAULT 3,
            error_message               TEXT,
            execution_time_ms           INTEGER,
            result_summary_json         TEXT,
            next_retry_at               TEXT,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_job_name
        ON scheduler_jobs(job_name)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_status
        ON scheduler_jobs(status)
    """)

    # Table des tokens de reset mot de passe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id                          INTEGER PRIMARY KEY,
            user_id                     INTEGER NOT NULL,
            token_hash                  TEXT NOT NULL UNIQUE,
            expires_at                  TEXT NOT NULL,
            used_at                     TEXT,
            created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_reset_tokens_token_hash
        ON password_reset_tokens(token_hash)
    """)

    conn.commit()
