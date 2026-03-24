"""
Migration 005 — Features physiques, HT et arbitre.
Ajoute les colonnes shots, corners, possession, HT, fatigue et referee
dans match_features.
"""

import sqlite3

DESCRIPTION = "Features shots/corners/possession/HT/fatigue/arbitre dans match_features"

_NOUVELLES_COLONNES = [
    # Shots domicile
    ("home_shots_avg_5m",            "REAL"),
    ("home_shots_on_target_avg_5m",  "REAL"),
    ("home_conversion_rate_5m",      "REAL"),
    ("home_shot_efficiency_5m",      "REAL"),
    # Corners domicile
    ("home_corners_avg_5m",          "REAL"),
    # Possession domicile
    ("home_possession_avg_5m",       "REAL"),
    # Mi-temps domicile
    ("home_goals_ht_avg_5m",         "REAL"),
    ("home_over15_ht_rate_5m",       "REAL"),
    # Fatigue domicile
    ("home_fatigue_score",           "REAL"),

    # Shots extérieur
    ("away_shots_avg_5m",            "REAL"),
    ("away_shots_on_target_avg_5m",  "REAL"),
    ("away_conversion_rate_5m",      "REAL"),
    ("away_shot_efficiency_5m",      "REAL"),
    # Corners extérieur
    ("away_corners_avg_5m",          "REAL"),
    # Possession extérieur
    ("away_possession_avg_5m",       "REAL"),
    # Mi-temps extérieur
    ("away_goals_ht_avg_5m",         "REAL"),
    ("away_over15_ht_rate_5m",       "REAL"),
    # Fatigue extérieur
    ("away_fatigue_score",           "REAL"),

    # Arbitre
    ("referee_avg_goals",            "REAL"),
    ("referee_home_bias",            "REAL"),
    ("referee_goals_volatility",     "REAL"),
]


def appliquer(conn: sqlite3.Connection) -> None:
    """
    Ajoute les nouvelles colonnes à match_features via ALTER TABLE.
    Ignore les colonnes déjà présentes.
    """
    cursor = conn.execute("PRAGMA table_info(match_features)")
    colonnes_existantes = {row["name"] for row in cursor.fetchall()}

    for nom, type_col in _NOUVELLES_COLONNES:
        if nom not in colonnes_existantes:
            conn.execute(
                f"ALTER TABLE match_features ADD COLUMN {nom} {type_col}"
            )

    conn.commit()
