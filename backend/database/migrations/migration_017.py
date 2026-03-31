"""
Migration 017 — Features mi-temps pour 1X2 HT.

Ajoute les colonnes de taux de résultat à la mi-temps dans `match_features` :
- home_ht_win_rate_5m  : % matchs où l'équipe domicile menait à la pause (5 derniers)
- away_ht_win_rate_5m  : % matchs où l'équipe extérieur menait à la pause
- home_ht_draw_rate_5m : % matchs avec score nul à la pause (domicile)
- away_ht_draw_rate_5m : % matchs avec score nul à la pause (extérieur)

Ces features permettent d'entraîner les marchés 1x2_ht_home, 1x2_ht_draw, 1x2_ht_away.
"""

import sqlite3

DESCRIPTION = "Ajout features mi-temps ht_win_rate/ht_draw_rate pour marchés 1X2 HT"


def appliquer(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(match_features)").fetchall()}

    nouvelles = [
        "home_ht_win_rate_5m",
        "away_ht_win_rate_5m",
        "home_ht_draw_rate_5m",
        "away_ht_draw_rate_5m",
    ]
    for col in nouvelles:
        if col not in cols:
            conn.execute(f"ALTER TABLE match_features ADD COLUMN {col} REAL")

    conn.commit()
