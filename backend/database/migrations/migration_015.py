"""
Migration 015 — Traçabilité des pronostics remplacés.

Ajoute la colonne `superseded_reason` à la table `pronostics`.
Quand le scheduler régénère les pronostics, les anciens `pending`
passent en status='superseded' avec une raison, au lieu d'être
supprimés (DELETE) — ce qui permettait zéro traçabilité.
"""

import sqlite3

DESCRIPTION = "Ajout colonne superseded_reason pour traçabilité des opportunités remplacées"


def appliquer(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pronostics)").fetchall()}

    if "superseded_reason" not in cols:
        conn.execute(
            "ALTER TABLE pronostics ADD COLUMN superseded_reason TEXT"
        )

    conn.commit()
