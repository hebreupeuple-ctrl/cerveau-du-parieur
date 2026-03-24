"""
Migration 003 — Sécurité, verrous distribués et audit bankroll.
"""

import sqlite3

from backend.core.config import settings

DESCRIPTION = "Sécurité, verrous distribués et audit bankroll"


def appliquer(conn: sqlite3.Connection) -> None:
    if not _colonne_existe(conn, "users", "is_admin"):
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0
            """
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduler_locks (
            job_name             TEXT PRIMARY KEY,
            lock_token           TEXT NOT NULL,
            owner_id             TEXT NOT NULL,
            acquired_at          TEXT NOT NULL,
            lock_expires_at      TEXT NOT NULL,
            updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_scheduler_locks_expires_at
        ON scheduler_locks(lock_expires_at)
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bankroll_transactions (
            id                   INTEGER PRIMARY KEY,
            user_id              INTEGER NOT NULL,
            pronostic_id         INTEGER,
            transaction_type     TEXT NOT NULL,
            amount               REAL NOT NULL,
            balance_before       REAL NOT NULL,
            balance_after        REAL NOT NULL,
            reference_note       TEXT,
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            FOREIGN KEY (pronostic_id) REFERENCES pronostics(id)
                ON DELETE SET NULL
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bankroll_transactions_user_id
        ON bankroll_transactions(user_id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bankroll_transactions_pronostic_id
        ON bankroll_transactions(pronostic_id)
        """
    )

    _promouvoir_admins(conn)
    conn.commit()


def _colonne_existe(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()
    return any(row["name"] == column_name for row in rows)


def _promouvoir_admins(conn: sqlite3.Connection) -> None:
    admin_emails = settings.admin_emails
    if admin_emails:
        placeholders = ", ".join("?" for _ in admin_emails)
        conn.execute(
            f"""
            UPDATE users
            SET is_admin = 1
            WHERE lower(email) IN ({placeholders})
            """,
            tuple(admin_emails),
        )

    count_admins = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_admin = 1"
    ).fetchone()[0]

    if count_admins > 0:
        return

    first_user = conn.execute(
        "SELECT id FROM users ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if first_user:
        conn.execute(
            "UPDATE users SET is_admin = 1 WHERE id = ?",
            (first_user["id"],),
        )
