"""
Migration 026 — Colonnes cartons dans match_features.

Ajoute les features de discipline (cartons jaunes/rouges) calculées
à partir des 5 derniers matchs de chaque équipe.
"""

import sqlite3

DESCRIPTION = "Colonnes cartons (yellow/red cards avg) dans match_features"

_NOUVELLES_COLONNES = [
    ("home_yellow_cards_avg_5m",  "REAL"),
    ("home_red_cards_avg_5m",     "REAL"),
    ("home_discipline_score_5m",  "REAL"),
    ("away_yellow_cards_avg_5m",  "REAL"),
    ("away_red_cards_avg_5m",     "REAL"),
    ("away_discipline_score_5m",  "REAL"),
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
