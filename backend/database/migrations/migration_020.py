"""
Migration 020 — Persistance des matrices de scores exacts dans pronostics.
"""

import sqlite3

DESCRIPTION = "Ajout colonne score_matrix_json dans pronostics"


def appliquer(conn: sqlite3.Connection) -> None:
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(pronostics)").fetchall()
    }
    if "score_matrix_json" in cols:
        return

    conn.execute(
        "ALTER TABLE pronostics ADD COLUMN score_matrix_json TEXT"
    )
