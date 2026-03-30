"""
Migration 016 — Tracking Closing Line Value (CLV).

Ajoute les colonnes `closing_odds` et `clv` à la table `pronostics`.
- closing_odds : cote du bookmaker au moment du coup d'envoi (ou proche)
- clv : (reference_odds / closing_odds - 1) × 100
  positif = on a eu une meilleure cote que le marché final → edge réel confirmé
  négatif = le marché avait raison contre nous

Ces deux colonnes permettent de mesurer si le modèle bat réellement le marché.
"""

import sqlite3

DESCRIPTION = "Ajout colonnes closing_odds et clv pour mesure du Closing Line Value"


def appliquer(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pronostics)").fetchall()}

    if "closing_odds" not in cols:
        conn.execute(
            "ALTER TABLE pronostics ADD COLUMN closing_odds REAL"
        )
    if "clv" not in cols:
        conn.execute(
            "ALTER TABLE pronostics ADD COLUMN clv REAL"
        )

    conn.commit()
