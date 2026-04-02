"""
Migration 022 — Suppression des comptes de test en production.

Supprime les comptes test@cerveau.com et audit@test.com ainsi que
toutes leurs données associées (pronostics, tokens, etc.).
"""

import sqlite3

DESCRIPTION = "Suppression comptes de test (test@cerveau.com, audit@test.com)"

EMAILS_TEST = ("test@cerveau.com", "audit@test.com")


def appliquer(conn: sqlite3.Connection) -> None:
    placeholders = ",".join("?" for _ in EMAILS_TEST)
    user_ids = [
        row["id"]
        for row in conn.execute(
            f"SELECT id FROM users WHERE email IN ({placeholders})",
            EMAILS_TEST,
        ).fetchall()
    ]

    if not user_ids:
        return

    id_placeholders = ",".join("?" for _ in user_ids)

    for table in (
        "pronostics",
        "user_markets",
        "user_leagues",
        "user_tokens",
        "user_devices",
        "bankroll_transactions",
        "notifications_log",
        "password_reset_tokens",
    ):
        conn.execute(
            f"DELETE FROM {table} WHERE user_id IN ({id_placeholders})",
            user_ids,
        )

    conn.execute(
        f"DELETE FROM users WHERE id IN ({id_placeholders})",
        user_ids,
    )
    conn.commit()
