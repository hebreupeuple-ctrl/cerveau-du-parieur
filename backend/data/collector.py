"""
Collecteur principal de données FootyStats.
"""

import asyncio
import sqlite3
from typing import Optional
from backend.core.logging import get_logger
from backend.data.footystats.client import FootyStatsClient
from backend.data.footystats.endpoints import FootyStatsEndpoints
from backend.data.footystats.parsers.leagues import (
    extraire_annee_saison,
    extraire_saison_principale,
    formater_nom_saison,
)
from backend.data.footystats.parsers.matches import parser_match
from backend.database.connection import obtenir_connexion
from backend.database.repositories.league_repository import LeagueRepository
from backend.database.repositories.team_repository import TeamRepository
from backend.database.repositories.match_repository import MatchRepository

logger = get_logger(__name__)

# Mapping des ligues principales avec leurs noms FootyStats
LIGUES_PRINCIPALES = {
    "England Premier League": {
        "country": "England",
        "priority": 1,
    },
    "Spain La Liga": {
        "country": "Spain",
        "priority": 1,
    },
    "Italy Serie A": {
        "country": "Italy",
        "priority": 1,
    },
    "Germany Bundesliga": {
        "country": "Germany",
        "priority": 1,
    },
    "France Ligue 1": {
        "country": "France",
        "priority": 1,
    },
    "Europe UEFA Champions League": {
        "country": "Europe",
        "priority": 1,
    },
}


class DataCollector:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()
        self.client = FootyStatsClient()
        self.league_repo = LeagueRepository(self.conn)
        self.team_repo = TeamRepository(self.conn)
        self.match_repo = MatchRepository(self.conn)

    async def collecter_ligues_et_saisons(self) -> list:
        """
        Collecte les ligues et saisons depuis FootyStats.
        Retourne la liste des saisons actives pour les ligues principales.
        """
        logger.info("Collecte des ligues depuis FootyStats...")

        response = await self.client.get(
            "league-list",
            params={"chosen_leagues_only": "true"},
        )

        data = response.get("data", [])
        if not isinstance(data, list):
            logger.warning("Format de réponse inattendu pour league-list")
            return []

        saisons_actives = []

        for ligue_data in data:
            nom = ligue_data.get("name", "")
            league_footystats_id = ligue_data.get("id")

            if nom not in LIGUES_PRINCIPALES or not league_footystats_id:
                continue

            config = LIGUES_PRINCIPALES[nom]
            derniere_saison = extraire_saison_principale(ligue_data)

            if not derniere_saison:
                continue

            # Sauvegarder la ligue
            league_id = self.league_repo.sauvegarder({
                "footystats_id": league_footystats_id,
                "name": nom,
                "country": config["country"],
                "tier": 1,
                "group_type": "major_european",
                "priority": config["priority"],
            })

            # Construire l'année lisible
            annee = extraire_annee_saison(derniere_saison)
            nom_saison = formater_nom_saison(derniere_saison)

            # Sauvegarder la saison
            season_db_id = await self._sauvegarder_saison(
                footystats_id=derniere_saison["id"],
                league_id=league_id,
                nom=nom_saison,
                annee=annee,
                country=derniere_saison.get("country", config["country"]),
            )

            saisons_actives.append({
                "league_name": nom,
                "league_id": league_id,
                "season_db_id": season_db_id,
                "footystats_season_id": derniere_saison["id"],
                "nom_saison": nom_saison,
            })

            logger.info_ctx(
                "Ligue initialisée",
                context={
                    "ligue": nom,
                    "saison": nom_saison,
                    "footystats_id": derniere_saison["id"],
                },
            )

        logger.info_ctx(
            "Ligues et saisons collectées",
            context={"count": len(saisons_actives)},
        )

        return saisons_actives

    async def _sauvegarder_saison(
        self,
        footystats_id: int,
        league_id: int,
        nom: str,
        annee: int,
        country: str,
    ) -> int:
        """Insère ou retourne l'ID d'une saison."""
        existante = self.conn.execute(
            "SELECT id FROM seasons WHERE footystats_id = ?",
            (footystats_id,),
        ).fetchone()

        if existante:
            return existante["id"]

        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO seasons (
                footystats_id, league_id, name,
                year, start_date, end_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                footystats_id,
                league_id,
                nom,
                annee,
                f"{annee}-08-01",
                f"{annee + 1}-05-31",
                "active",
            ),
        )
        self.conn.commit()

        if cursor.lastrowid:
            return cursor.lastrowid

        row = self.conn.execute(
            "SELECT id FROM seasons WHERE footystats_id = ?",
            (footystats_id,),
        ).fetchone()
        return row["id"] if row else None

    async def collecter_matchs_saison(
        self,
        season_id: int,
        league_id: int,
        footystats_season_id: int,
        max_time: int = None,
    ) -> dict:
        """
        Collecte tous les matchs d'une saison.
        """
        total = 0
        nouveaux = 0
        erreurs = 0
        page_courante = 1
        total_pages = 1

        while page_courante <= total_pages:
            params = {
                "season_id": footystats_season_id,
                "page": page_courante,
                "max_per_page": 500,
            }
            if max_time:
                params["max_time"] = max_time

            try:
                response = await self.client.get(
                    "league-matches",
                    params=params,
                )

                pager = response.get("pager", {})
                total_pages = pager.get("total_pages", 1)

                matchs_data = response.get("data", [])
                if not isinstance(matchs_data, list):
                    break

                for match_data in matchs_data:
                    resultat = await self._traiter_match(
                        match_data=match_data,
                        season_id=season_id,
                        league_id=league_id,
                    )
                    if resultat == "nouveau":
                        nouveaux += 1
                        total += 1
                    elif resultat == "existant":
                        total += 1
                    else:
                        erreurs += 1

                logger.info_ctx(
                    f"Page {page_courante}/{total_pages}",
                    context={
                        "season_id": footystats_season_id,
                        "matchs": len(matchs_data),
                        "nouveaux_cumul": nouveaux,
                    },
                )

                page_courante += 1
                await asyncio.sleep(1)

            except Exception as e:
                logger.error_ctx(
                    f"Erreur collecte page {page_courante}",
                    context={
                        "season_id": footystats_season_id,
                        "erreur": str(e),
                    },
                )
                break

        return {
            "total": total,
            "nouveaux": nouveaux,
            "erreurs": erreurs,
            "pages": total_pages,
        }

    async def _traiter_match(
        self,
        match_data: dict,
        season_id: int,
        league_id: int,
    ) -> str:
        try:
            match_parsed = parser_match(match_data)
            if not match_parsed:
                return "erreur"

            home_id = await self._obtenir_ou_creer_equipe(
                match_data.get("homeID"),
                match_data.get("home_name", "Unknown"),
            )
            away_id = await self._obtenir_ou_creer_equipe(
                match_data.get("awayID"),
                match_data.get("away_name", "Unknown"),
            )

            if not home_id or not away_id:
                return "erreur"

            existant = self.match_repo.trouver_par_footystats_id(
                match_parsed["footystats_id"]
            )

            match_id = self.match_repo.sauvegarder(
                match=match_parsed,
                season_id=season_id,
                league_id=league_id,
                home_team_id=home_id,
                away_team_id=away_id,
            )

            if match_id and not existant:
                return "nouveau"
            return "existant"

        except Exception as e:
            logger.error_ctx(
                "Erreur traitement match",
                context={
                    "match_id": match_data.get("id"),
                    "erreur": str(e),
                },
            )
            return "erreur"

    async def _obtenir_ou_creer_equipe(
        self,
        footystats_id: int,
        nom: str,
    ) -> Optional[int]:
        if not footystats_id:
            return None

        equipe = self.team_repo.trouver_par_footystats_id(footystats_id)
        if equipe:
            return equipe["id"]

        return self.team_repo.sauvegarder({
            "footystats_id": footystats_id,
            "name": nom,
            "country": "Unknown",
        })

    async def collecter_matchs_aujourdhui(self) -> dict:
        """
        Collecte les matchs d'aujourd'hui.
        """
        logger.info("Collecte des matchs d'aujourd'hui...")

        try:
            response = await self.client.get(
                "todays-matches",
                params={"timezone": "UTC"},
            )

            matchs_data = response.get("data", [])
            if not isinstance(matchs_data, list):
                matchs_data = []

            total = 0
            nouveaux = 0

            for match_data in matchs_data:
                league_id_fs = match_data.get("competition_id")
                if not league_id_fs:
                    continue

                ligue = self.league_repo.trouver_par_footystats_id(
                    league_id_fs
                )
                if not ligue:
                    continue

                saison_row = self.conn.execute(
                    """
                    SELECT id FROM seasons
                    WHERE league_id = ? AND status = 'active'
                    ORDER BY year DESC LIMIT 1
                    """,
                    (ligue["id"],),
                ).fetchone()

                if not saison_row:
                    continue

                resultat = await self._traiter_match(
                    match_data=match_data,
                    season_id=saison_row["id"],
                    league_id=ligue["id"],
                )
                total += 1
                if resultat == "nouveau":
                    nouveaux += 1

            logger.info_ctx(
                "Matchs du jour collectés",
                context={"total": total, "nouveaux": nouveaux},
            )

            return {"total": total, "nouveaux": nouveaux}

        except Exception as e:
            logger.error_ctx(
                "Erreur collecte matchs du jour",
                context={"erreur": str(e)},
            )
            return {"total": 0, "nouveaux": 0}

    async def fermer(self) -> None:
        await self.client.fermer()
