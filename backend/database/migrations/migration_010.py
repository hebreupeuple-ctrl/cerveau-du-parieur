"""
Migration 010 — Index composites sur pronostics pour accélérer /today et /history.
"""

import sqlite3

DESCRIPTION = "Index composites pronostics(user_id, status) et pronostics(match_id)"


def appliquer(conn: sqlite3.Connection) -> None:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_pronostics_user_status'"
    )
    if cursor.fetchone() is None:
        conn.execute(
            """
            CREATE INDEX idx_pronostics_user_status
            ON pronostics(user_id, status)
            """
        )

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_pronostics_match_id'"
    )
    if cursor.fetchone() is None:
        conn.execute(
            """
            CREATE INDEX idx_pronostics_match_id
            ON pronostics(match_id)
            """
        )

    conn.commit()
