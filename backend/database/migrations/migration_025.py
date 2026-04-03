"""
Migration 025 — Marchés dc_1x et dc_x2 activés par défaut pour tous les utilisateurs.

dc_1x (domicile ou nul) et dc_x2 (nul ou extérieur) sont entièrement câblés dans
le pipeline de value betting mais absents de user_markets → jamais générés.
"""

import sqlite3

DESCRIPTION = "Marchés dc_1x et dc_x2 activés par défaut dans user_markets"

MARCHES_A_AJOUTER = ("dc_1x", "dc_x2")


def appliquer(conn: sqlite3.Connection) -> None:
    user_ids = [
        row["id"]
        for row in conn.execute("SELECT id FROM users").fetchall()
    ]

    for user_id in user_ids:
        for market in MARCHES_A_AJOUTER:
            conn.execute(
                "INSERT OR IGNORE INTO user_markets (user_id, market) VALUES (?, ?)",
                (user_id, market),
            )

    conn.commit()
