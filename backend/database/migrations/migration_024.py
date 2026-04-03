"""
Migration 024 — Colonnes probabilités implicites bookmaker dans match_features.

Ajoute les features bk_prob_* qui capturent le consensus du marché bookmaker
directement dans la table match_features pour l'entraînement ML.
"""

import sqlite3

DESCRIPTION = "Colonnes bk_prob_* (odds implicites bookmaker) dans match_features"

_NOUVELLES_COLONNES = [
    ("bk_prob_home",   "REAL"),
    ("bk_prob_draw",   "REAL"),
    ("bk_prob_away",   "REAL"),
    ("bk_prob_over15", "REAL"),
    ("bk_prob_over25", "REAL"),
    ("bk_prob_btts",   "REAL"),
    ("bk_margin",      "REAL"),
    ("bk_has_odds",    "REAL"),
]


def appliquer(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("PRAGMA table_info(match_features)")
    colonnes_existantes = {row["name"] for row in cursor.fetchall()}

    for nom, type_col in _NOUVELLES_COLONNES:
        if nom not in colonnes_existantes:
            conn.execute(
                f"ALTER TABLE match_features ADD COLUMN {nom} {type_col}"
            )

    conn.commit()
