"""
Migration 018 — Cotes Double Chance et HT 1X2 dans la table odds.

Ajoute les colonnes manquantes pour stocker les cotes DC et mi-temps
directement depuis l'API FootyStats (odds_doublechance_*, odds_1st_half_result_*).
"""

import sqlite3

DESCRIPTION = "Ajout cotes DC (1X/X2/12) et HT 1X2 dans la table odds"


def appliquer(conn: sqlite3.Connection) -> None:
    colonnes = [
        ("odds_dc_1x",   "REAL"),
        ("odds_dc_x2",   "REAL"),
        ("odds_dc_12",   "REAL"),
        ("odds_ht_home", "REAL"),
        ("odds_ht_draw", "REAL"),
        ("odds_ht_away", "REAL"),
    ]
    existing = {row[1] for row in conn.execute("PRAGMA table_info(odds)").fetchall()}
    for col_name, col_type in colonnes:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE odds ADD COLUMN {col_name} {col_type}")
    conn.commit()
