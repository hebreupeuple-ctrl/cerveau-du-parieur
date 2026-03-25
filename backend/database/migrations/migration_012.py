"""
Migration 012 — Contrainte UNIQUE sur pronostics(user_id, match_id, market).

Sans cette contrainte, deux appels simultanés à la génération (ex: double refresh
dans l'app) insèrent des pronostics identiques pour le même match/marché.
"""

import sqlite3

DESCRIPTION = "Contrainte UNIQUE pronostics(user_id, match_id, market) + dédoublonnage"


def appliquer(conn: sqlite3.Connection) -> None:
    # Vérifier si l'index existe déjà
    existing = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_pronostics_unique_pending'
        """
    ).fetchone()
    if existing:
        return

    # Supprimer les doublons parmi les pronostics actifs (pending/placed).
    # On garde le plus récent (id MAX) par (user_id, match_id, market).
    # On cible uniquement pending/placed car l'index UNIQUE ne couvre que ces statuts.
    conn.execute(
        """
        DELETE FROM pronostics
        WHERE status IN ('pending', 'placed')
        AND id NOT IN (
            SELECT MAX(id)
            FROM pronostics
            WHERE status IN ('pending', 'placed')
            GROUP BY user_id, match_id, market
        )
        """
    )

    # Index UNIQUE sur les pronostics pending/placed uniquement :
    # un utilisateur ne peut avoir qu'un seul pronostic actif par (match, marché).
    # Les pronostics résolus (won/lost/void/ignored) restent historiques sans contrainte.
    conn.execute(
        """
        CREATE UNIQUE INDEX idx_pronostics_unique_pending
        ON pronostics(user_id, match_id, market)
        WHERE status IN ('pending', 'placed')
        """
    )

    conn.commit()
