"""
Migration 009 — Activation des marchés 1x2 pour tous les utilisateurs actifs.
"""

import sqlite3

DESCRIPTION = "Activation marchés 1x2 (home/draw/away) pour tous les utilisateurs"


def appliquer(conn: sqlite3.Connection) -> None:
    users = conn.execute("SELECT id FROM users").fetchall()
    for user in users:
        for market in ("1x2_home", "1x2_draw", "1x2_away"):
            conn.execute(
                """
                INSERT OR IGNORE INTO user_markets (user_id, market, is_active)
                VALUES (?, ?, 1)
                """,
                (user["id"], market),
            )
    conn.commit()
