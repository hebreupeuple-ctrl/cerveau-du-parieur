"""
Synchronisation automatique des ligues depuis FootyStats.
Au demarrage, on synchronise notre base avec les ligues
exactement disponibles dans le package de l'utilisateur.
"""

import sqlite3
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion
from backend.data.footystats.client import FootyStatsClient

logger = get_logger(__name__)

LIGUES_PRIORITE = {
    "England Premier League": 1,
    "Spain La Liga": 1,
    "Italy Serie A": 1,
    "Germany Bundesliga": 1,
    "France Ligue 1": 1,
    "Europe UEFA Champions League": 1,
    "Europe UEFA Europa League": 2,
    "Europe UEFA Europa Conference League": 2,
    "England Championship": 2,
    "England EFL League One": 2,
    "England EFL League Two": 2,
    "England National League": 3,
    "Portugal Liga NOS": 2,
    "Netherlands Eredivisie": 2,
    "Turkey Süper Lig": 2,
    "Scotland Premiership": 2,
    "Belgium Pro League": 2,
    "Greece Super League": 3,
    "Russia Russian Premier League": 3,
    "Brazil Serie A": 2,
    "Brazil Serie B": 3,
    "Argentina Primera División": 2,
    "Mexico Liga MX": 2,
    "USA MLS": 2,
    "Japan J1 League": 3,
    "South Korea K League 1": 3,
    "Australia A-League": 3,
}


async def synchroniser_ligues(
    conn: sqlite3.Connection = None
) -> dict:
    """
    Synchronise les ligues disponibles dans le package FootyStats
    avec notre base de données.

    Retourne un résumé des changements effectués.
    """
    if conn is None:
        conn = obtenir_connexion()

    client = FootyStatsClient()

    logger.info("Synchronisation des ligues depuis FootyStats...")

    try:
        response = await client.get(
            "league-list",
            params={"chosen_leagues_only": "true"},
        )
    except Exception as e:
        logger.error_ctx(
            "Erreur synchronisation ligues",
            context={"erreur": str(e)},
        )
        return {"erreur": str(e)}

    data = response.get("data", [])
    if not isinstance(data, list):
        logger.warning("Format inattendu pour league-list")
        return {"erreur": "Format inattendu"}

    ligues_footystats = {}

    for ligue_data in data:
        nom = ligue_data.get("name", "")
        country = ligue_data.get("country", "Unknown")
        ligue_footystats_id = ligue_data.get("id")
        saisons = ligue_data.get("season", [])

        if not ligue_footystats_id or not isinstance(saisons, list) or not saisons:
            continue

        derniere_saison = max(
            saisons,
            key=lambda s: s.get("year", 0)
        )

        annee = str(derniere_saison.get("year", ""))
        if len(annee) == 8:
            nom_saison = f"{annee[:4]}/{annee[4:]}"
        else:
            nom_saison = annee

        ligues_footystats[nom] = {
            "league_footystats_id": ligue_footystats_id,
            "footystats_season_id": derniere_saison["id"],
            "country": country,
            "nom_saison": nom_saison,
            "annee": int(annee[:4]) if annee else 2025,
            "priorite": LIGUES_PRIORITE.get(nom, 3),
        }

    ajoutees = 0
    mises_a_jour = 0
    desactivees = 0

    for nom, info in ligues_footystats.items():
        ligue_db = conn.execute(
            "SELECT * FROM leagues WHERE name = ?",
            (nom,),
        ).fetchone()

        if not ligue_db:
            cursor = conn.execute(
                """
                INSERT INTO leagues (
                    footystats_id, name, country,
                    tier, group_type, is_active, priority
                ) VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    info["league_footystats_id"],
                    nom,
                    info["country"],
                    1,
                    _determiner_groupe(nom),
                    info["priorite"],
                ),
            )
            league_id = cursor.lastrowid

            await _synchroniser_saison(
                conn=conn,
                league_id=league_id,
                info=info,
            )

            ajoutees += 1
            logger.info_ctx(
                "Nouvelle ligue ajoutée",
                context={"ligue": nom, "saison": info["nom_saison"]},
            )
        else:
            conn.execute(
                """
                UPDATE leagues SET
                    footystats_id = ?,
                    country = ?,
                    is_active = 1,
                    priority = ?,
                    updated_at = datetime('now')
                WHERE name = ?
                """,
                (
                    info["league_footystats_id"],
                    info["country"],
                    info["priorite"],
                    nom,
                ),
            )

            await _synchroniser_saison(
                conn=conn,
                league_id=ligue_db["id"],
                info=info,
            )

            mises_a_jour += 1

    ligues_actives_db = conn.execute(
        "SELECT name FROM leagues WHERE is_active = 1"
    ).fetchall()

    noms_actifs_db = {row["name"] for row in ligues_actives_db}
    noms_footystats = set(ligues_footystats.keys())

    for nom_a_desactiver in noms_actifs_db - noms_footystats:
        conn.execute(
            "UPDATE leagues SET is_active = 0 WHERE name = ?",
            (nom_a_desactiver,),
        )
        desactivees += 1
        logger.info_ctx(
            "Ligue désactivée",
            context={"ligue": nom_a_desactiver},
        )

    conn.commit()

    cursor = conn.execute(
        "SELECT COUNT(*) FROM leagues WHERE is_active = 1"
    )
    total_actives = cursor.fetchone()[0]

    resultat = {
        "total_footystats": len(ligues_footystats),
        "ajoutees": ajoutees,
        "mises_a_jour": mises_a_jour,
        "desactivees": desactivees,
        "total_actives_db": total_actives,
    }

    logger.info_ctx(
        "Synchronisation ligues terminée",
        context=resultat,
    )

    await client.fermer()
    return resultat


async def _synchroniser_saison(
    conn: sqlite3.Connection,
    league_id: int,
    info: dict,
) -> None:
    """
    Synchronise la saison active d'une ligue.
    """
    saison_existante = conn.execute(
        "SELECT id FROM seasons WHERE footystats_id = ?",
        (info["footystats_season_id"],),
    ).fetchone()

    if saison_existante:
        conn.execute(
            "UPDATE seasons SET status = 'active' WHERE id = ?",
            (saison_existante["id"],),
        )
        return

    conn.execute(
        """
        UPDATE seasons SET status = 'complete'
        WHERE league_id = ? AND status = 'active'
        """,
        (league_id,),
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO seasons (
            footystats_id, league_id, name,
            year, start_date, end_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            info["footystats_season_id"],
            league_id,
            info["nom_saison"],
            info["annee"],
            f"{info['annee']}-07-01",
            f"{info['annee'] + 1}-06-30",
            ),
        )


def _determiner_groupe(nom_ligue: str) -> str:
    """
    Détermine le groupe d'une ligue selon son nom.
    """
    if any(pays in nom_ligue for pays in [
        "England", "Spain", "Italy", "Germany",
        "France", "Europe UEFA Champions"
    ]):
        return "major_european"
    elif any(pays in nom_ligue for pays in [
        "Portugal", "Netherlands", "Turkey",
        "Scotland", "Belgium", "Russia",
        "Brazil", "Argentina", "Mexico"
    ]):
        return "secondary_european"
    else:
        return "other"


async def collecter_nouvelles_ligues(
    conn: sqlite3.Connection = None,
) -> dict:
    """
    Après synchronisation, collecte ou rafraîchit
    les saisons actives des ligues disponibles.
    """
    if conn is None:
        conn = obtenir_connexion()

    from backend.data.collector import DataCollector
    collector = DataCollector(conn)

    saisons_actives = conn.execute(
        """
        SELECT l.id, l.name, s.id as season_id,
               s.footystats_id as fs_season_id,
               COUNT(m.id) as matches_count
        FROM leagues l
        JOIN seasons s ON s.league_id = l.id
        LEFT JOIN matches m ON m.season_id = s.id
        WHERE l.is_active = 1
        AND s.status = 'active'
        GROUP BY l.id, l.name, s.id, s.footystats_id
        ORDER BY l.priority ASC, l.name ASC
        """,
    ).fetchall()

    logger.info_ctx(
        "Saisons actives à collecter",
        context={"count": len(saisons_actives)},
    )

    resultats = {}
    for ligue in saisons_actives:
        logger.info_ctx(
            "Collecte saison active",
            context={
                "ligue": ligue["name"],
                "matches_count": ligue["matches_count"],
            },
        )
        res = await collector.collecter_matchs_saison(
            season_id=ligue["season_id"],
            league_id=ligue["id"],
            footystats_season_id=ligue["fs_season_id"],
        )
        resultats[ligue["name"]] = res

    await collector.fermer()
    return resultats
