"""
Migration 006 — Colonnes odds mi-temps (over15_ht).
Ajoute odds_over15_ht, odds_under15_ht et prob_over15_ht_corrected
dans la table odds, référencées par value_betting.py mais absentes du schéma.
"""

import sqlite3

DESCRIPTION = "Colonnes odds over15_ht dans la table odds"

_NOUVELLES_COLONNES = [
    ("odds_over15_ht",          "REAL"),
    ("odds_under15_ht",         "REAL"),
    ("prob_over15_ht_corrected", "REAL"),
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
