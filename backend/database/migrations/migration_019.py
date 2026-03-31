"""
Migration 019 — Colonnes H2H en REAL pour le decay temporel.

Les colonnes h2h_home_wins_5, h2h_draws_5, h2h_away_wins_5 étaient INTEGER.
Avec le decay exponentiel, elles contiennent des valeurs flottantes (ex: 0.987).
SQLite tronquait silencieusement vers 0.

SQLite ne supporte pas ALTER COLUMN TYPE : on recrée la table via rename+copy.
"""

import re
import sqlite3

DESCRIPTION = "Colonnes H2H (wins/draws) en REAL pour decay temporel"


def appliquer(conn: sqlite3.Connection) -> None:
    # Vérifier si déjà REAL
    cols = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(match_features)").fetchall()}
    if cols.get("h2h_home_wins_5", "").upper() == "REAL":
        return  # Déjà correct

    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='match_features'"
    ).fetchone()
    if not row:
        return

    original_ddl = row[0]

    # Remplacer INTEGER par REAL pour les 3 colonnes H2H (avec espaces variables)
    new_ddl = re.sub(
        r'(h2h_home_wins_5\s+)INTEGER',
        r'\1REAL',
        original_ddl,
    )
    new_ddl = re.sub(r'(h2h_draws_5\s+)INTEGER',    r'\1REAL', new_ddl)
    new_ddl = re.sub(r'(h2h_away_wins_5\s+)INTEGER', r'\1REAL', new_ddl)

    if new_ddl == original_ddl:
        return  # Rien à changer

    # Récupérer les index existants
    indexes = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='match_features' AND sql IS NOT NULL"
    ).fetchall()

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")
    conn.execute("ALTER TABLE match_features RENAME TO match_features_old")
    conn.execute(new_ddl)
    conn.execute("INSERT INTO match_features SELECT * FROM match_features_old")
    conn.execute("DROP TABLE match_features_old")

    for (idx_sql,) in indexes:
        conn.execute(idx_sql)

    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
