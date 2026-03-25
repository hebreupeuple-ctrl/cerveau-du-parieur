"""
Migration 008 — Contrainte UNIQUE sur odds(match_id, bookmaker).
Supprime les doublons (garde le plus récent) puis crée l'index UNIQUE.
"""

import sqlite3


def appliquer(conn: sqlite3.Connection) -> None:
    # Vérifier si la contrainte existe déjà
    cursor = conn.execute("PRAGMA index_list(odds)")
    indices = [row["name"] for row in cursor.fetchall()]
    if "uq_odds_match_bookmaker" in indices:
        return

    # Supprimer les doublons en ne gardant que la ligne avec le id max (la plus récente)
    conn.execute(
        """
        DELETE FROM odds
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM odds
            GROUP BY match_id, bookmaker
        )
        """
    )

    # Créer l'index UNIQUE
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_odds_match_bookmaker
        ON odds (match_id, bookmaker)
        """
    )

    conn.commit()
