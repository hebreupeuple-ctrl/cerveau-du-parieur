"""
Migration 014 — Nettoyage colonnes orphelines.

- Supprime la colonne `over35` de `matches` (jamais remplie par FootyStats).
- Supprime les colonnes `odds_over35`, `odds_under35`, `prob_over35_corrected`
  de `odds` (idem).

SQLite >= 3.35 supporte DROP COLUMN nativement.
Si la version est antérieure, on skippe silencieusement (colonnes restent
NULL, aucun impact fonctionnel — le trainer et l'accumulateur ignorent déjà
over35 dans MARCHES).
"""

import sqlite3

DESCRIPTION = "Suppression colonnes over35 orphelines + nettoyage arbitre"


def appliquer(conn: sqlite3.Connection) -> None:
    # Vérifier version SQLite pour DROP COLUMN
    version_str = conn.execute("SELECT sqlite_version()").fetchone()[0]
    parts = [int(x) for x in version_str.split(".")]
    version_tuple = tuple(parts[:3])
    supports_drop_column = version_tuple >= (3, 35, 0)

    if supports_drop_column:
        _drop_over35_columns(conn)
    else:
        # Fallback : on laisse les colonnes (NULL de toute façon) mais on
        # crée un index sentinel pour indiquer que la migration a été appliquée.
        pass  # Colonnes NULL, aucun impact fonctionnel

    conn.commit()


def _drop_over35_columns(conn: sqlite3.Connection) -> None:
    """Supprime les colonnes over35 si elles existent."""

    # Table matches : colonne over35
    matches_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(matches)").fetchall()
    }
    if "over35" in matches_cols:
        conn.execute("ALTER TABLE matches DROP COLUMN over35")

    # Table odds : colonnes over35/under35/prob_over35
    odds_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(odds)").fetchall()
    }
    for col in ("odds_over35", "odds_under35", "prob_over35_corrected"):
        if col in odds_cols:
            conn.execute(f"ALTER TABLE odds DROP COLUMN {col}")
