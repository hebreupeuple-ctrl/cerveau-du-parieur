"""
Migration 007 — Colonnes ML over15_ht dans predictions.
Ajoute ml_prob_over15_ht et prob_over15_ht dans la table predictions,
calculées par le trainer mais absentes du schéma.
"""

import sqlite3

DESCRIPTION = "Colonnes ml_prob_over15_ht et prob_over15_ht dans predictions"

_NOUVELLES_COLONNES = [
    ("ml_prob_over15_ht", "REAL"),
    ("prob_over15_ht",    "REAL NOT NULL DEFAULT 0.5"),
]


def appliquer(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("PRAGMA table_info(predictions)")
    colonnes_existantes = {row["name"] for row in cursor.fetchall()}

    for nom, type_col in _NOUVELLES_COLONNES:
        if nom not in colonnes_existantes:
            conn.execute(
                f"ALTER TABLE predictions ADD COLUMN {nom} {type_col}"
            )

    conn.commit()
