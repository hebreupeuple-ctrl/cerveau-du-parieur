"""
Resynchronise les données de buts mi-temps (home_goals_ht / away_goals_ht)
pour toutes les saisons en base.

Le parser utilisait le mauvais nom de champ FootyStats ("team_a_ht_goals"
au lieu de "ht_goals_team_a"), ce qui laissait 100% des matchs avec NULL.
Ce script corrige le problème en refaisant la collecte saison par saison.

Usage :
    python scripts/resync_ht_goals.py [--leagues-only] [--limit N]

Options :
    --leagues-only  Ne resync que les ligues actives du compte (recommandé)
    --limit N       Traite au maximum N saisons (pour tester)

Exemples :
    python scripts/resync_ht_goals.py --leagues-only
    python scripts/resync_ht_goals.py --leagues-only --limit 5
    python scripts/resync_ht_goals.py          # toutes les saisons
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path

# Ajoute la racine du projet au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.connection import obtenir_connexion
from backend.data.collector import DataCollector
from backend.core.logging import get_logger

logger = get_logger("resync_ht")


def obtenir_saisons(conn, leagues_only: bool) -> list:
    """
    Retourne les saisons à resynchroniser, ordonnées du plus récent au plus ancien.
    Filtre sur les ligues actives si leagues_only=True.
    Exclut les saisons sans données HT manquantes.
    """
    if leagues_only:
        rows = conn.execute("""
            SELECT s.id, s.footystats_id, s.league_id, l.name as league_name,
                   s.name as season_name,
                   COUNT(m.id) as total,
                   SUM(CASE WHEN m.status='complete' AND m.home_goals_ht IS NULL
                            THEN 1 ELSE 0 END) as ht_null
            FROM seasons s
            JOIN leagues l ON s.league_id = l.id
            JOIN user_leagues ul ON ul.league_id = l.id AND ul.is_active = 1
            LEFT JOIN matches m ON m.season_id = s.id
            GROUP BY s.id
            HAVING ht_null > 0
            ORDER BY s.year DESC, l.name
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.id, s.footystats_id, s.league_id, l.name as league_name,
                   s.name as season_name,
                   COUNT(m.id) as total,
                   SUM(CASE WHEN m.status='complete' AND m.home_goals_ht IS NULL
                            THEN 1 ELSE 0 END) as ht_null
            FROM seasons s
            JOIN leagues l ON s.league_id = l.id
            LEFT JOIN matches m ON m.season_id = s.id
            GROUP BY s.id
            HAVING ht_null > 0
            ORDER BY s.year DESC, l.name
        """).fetchall()

    return [dict(r) for r in rows]


async def resync(leagues_only: bool, limit: int | None) -> None:
    conn = obtenir_connexion()
    saisons = obtenir_saisons(conn, leagues_only)

    if limit:
        saisons = saisons[:limit]

    total_saisons = len(saisons)
    total_ht_null = sum(s["ht_null"] or 0 for s in saisons)

    print(f"\n{'='*60}")
    print(f"Resync HT Goals — {total_saisons} saisons, ~{total_ht_null} matchs à corriger")
    print(f"{'='*60}\n")

    if not saisons:
        print("Aucune saison à resynchroniser. Terminé.")
        return

    collector = DataCollector(conn)
    debut = time.time()
    saisons_ok = 0
    saisons_ko = 0

    for i, saison in enumerate(saisons, 1):
        label = f"{saison['league_name']} {saison['season_name']}"
        print(f"[{i}/{total_saisons}] {label} ({saison['ht_null']} HT manquants)...", end=" ", flush=True)

        try:
            result = await collector.collecter_matchs_saison(
                season_id=saison["id"],
                league_id=saison["league_id"],
                footystats_season_id=saison["footystats_id"],
            )
            print(f"OK — {result['total']} matchs traités ({result['nouveaux']} nouveaux, {result['erreurs']} erreurs)")
            saisons_ok += 1
        except Exception as e:
            print(f"ERREUR — {e}")
            saisons_ko += 1

        # Pause entre saisons pour respecter le rate limit
        await asyncio.sleep(2)

    duree = round(time.time() - debut)
    print(f"\n{'='*60}")
    print(f"Terminé en {duree}s — {saisons_ok} saisons OK, {saisons_ko} en erreur")
    print(f"{'='*60}\n")

    # Vérification finale
    remaining = conn.execute("""
        SELECT COUNT(*) FROM matches
        WHERE status='complete' AND home_goals_ht IS NULL
    """).fetchone()[0]
    print(f"Matchs complets encore sans données HT : {remaining}")

    await collector.client.fermer()


def main():
    parser = argparse.ArgumentParser(description="Resync des données HT depuis FootyStats")
    parser.add_argument(
        "--leagues-only",
        action="store_true",
        help="Traite uniquement les ligues actives du compte",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximum de saisons à traiter",
    )
    args = parser.parse_args()

    asyncio.run(resync(leagues_only=args.leagues_only, limit=args.limit))


if __name__ == "__main__":
    main()
