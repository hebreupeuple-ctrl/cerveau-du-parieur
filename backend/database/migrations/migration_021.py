"""
Migration 021 — Nettoyage des marchés non supportés dans user_markets.

Supprime les entrées pour les marchés qui ne peuvent jamais générer
de pronostics (absents de mapping_marches dans value_betting.py) :
- under15, under25, under45 : jamais dans le pipeline de génération
- over35 : retiré du pipeline (aucune cote en DB)
- ng : jamais dans le pipeline de génération
"""

import sqlite3

DESCRIPTION = "Nettoyage marchés non supportés dans user_markets"

MARCHES_A_SUPPRIMER = ("under15", "under25", "under45", "over35", "ng")


def appliquer(conn: sqlite3.Connection) -> None:
    placeholders = ",".join("?" for _ in MARCHES_A_SUPPRIMER)
    conn.execute(
        f"DELETE FROM user_markets WHERE market IN ({placeholders})",
        MARCHES_A_SUPPRIMER,
    )
    conn.commit()
