"""
Migration 004 — Index de performance critiques.
Ajoute les index manquants sur les tables les plus interrogées.
"""

import sqlite3

DESCRIPTION = "Index de performance sur matches, features, pronostics et odds"


def appliquer(conn: sqlite3.Connection) -> None:
    """
    Crée les index manquants pour accélérer les requêtes fréquentes.
    """

    # matches : filtrage par statut + timestamp (scheduler, backfill, features)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_matches_status_timestamp
        ON matches(status, match_timestamp)
        """
    )

    # matches : lookup par league_id + timestamp (pronostics du jour, DC)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_matches_league_timestamp
        ON matches(league_id, match_timestamp)
        """
    )

    # matches : équipes domicile/extérieur (features de forme, H2H)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_matches_home_team_timestamp
        ON matches(home_team_id, match_timestamp)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_matches_away_team_timestamp
        ON matches(away_team_id, match_timestamp)
        """
    )

    # match_features : lookup par match_id (accumulateur, backfill)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_match_features_match_id
        ON match_features(match_id)
        """
    )

    # pronostics : filtrage par utilisateur + statut (endpoint pronostics)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pronostics_user_status
        ON pronostics(user_id, status)
        """
    )

    # pronostics : filtrage par match (résolution des résultats)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pronostics_match_id
        ON pronostics(match_id)
        """
    )

    # odds : dernières cotes par match (accumulateur)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_odds_match_bookmaker_tier
        ON odds(match_id, bookmaker_tier, collected_timestamp)
        """
    )

    # bankroll_transactions : historique par user
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bankroll_transactions_user_created
        ON bankroll_transactions(user_id, created_at)
        """
    )

    conn.commit()
