"""
Migration 023 — Colonnes odds over05_ht et over25_ht.
Ajoute odds_over05_ht, odds_under05_ht, odds_over25_ht, odds_under25_ht
et leurs probabilités corrigées dans la table odds.
"""

import sqlite3

DESCRIPTION = "Colonnes odds over05_ht et over25_ht dans la table odds"

_NOUVELLES_COLONNES = [
    ("odds_over05_ht",           "REAL"),
    ("odds_under05_ht",          "REAL"),
    ("odds_over25_ht",           "REAL"),
    ("odds_under25_ht",          "REAL"),
    ("prob_over05_ht_corrected", "REAL"),
    ("prob_over25_ht_corrected", "REAL"),
]


def appliquer(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("PRAGMA table_info(odds)")
    colonnes_existantes = {row["name"] for row in cursor.fetchall()}

    for nom, type_col in _NOUVELLES_COLONNES:
        if nom not in colonnes_existantes:
            conn.execute(
                f"ALTER TABLE odds ADD COLUMN {nom} {type_col}"
            )

    conn.commit()
