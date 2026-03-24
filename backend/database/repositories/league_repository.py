"""
Repository pour les ligues.
Toutes les opérations de base de données sur les ligues.
"""

import sqlite3
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion

logger = get_logger(__name__)


class LeagueRepository:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()

    def sauvegarder(self, ligue: dict) -> int:
        """
        Insère ou met à jour une ligue.
        Retourne l'ID de la ligue.
        """
        existante = self.trouver_par_footystats_id(
            ligue["footystats_id"]
        )

        if existante:
            self.conn.execute(
                """
                UPDATE leagues SET
                    name = ?,
                    country = ?,
                    updated_at = datetime('now')
                WHERE footystats_id = ?
                """,
                (
                    ligue["name"],
                    ligue.get("country", "Unknown"),
                    ligue["footystats_id"],
                ),
            )
            self.conn.commit()
            return existante["id"]

        cursor = self.conn.execute(
            """
            INSERT INTO leagues (
                footystats_id, name, country,
                tier, group_type, is_active, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ligue["footystats_id"],
                ligue["name"],
                ligue.get("country", "Unknown"),
                ligue.get("tier", 1),
                ligue.get("group_type", "major_european"),
                1,
                ligue.get("priority", 1),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def trouver_par_footystats_id(
        self, footystats_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = self.conn.execute(
            "SELECT * FROM leagues WHERE footystats_id = ?",
            (footystats_id,),
        )
        return cursor.fetchone()

    def trouver_par_id(
        self, league_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = self.conn.execute(
            "SELECT * FROM leagues WHERE id = ?",
            (league_id,),
        )
        return cursor.fetchone()

    def lister_actives(self) -> list:
        cursor = self.conn.execute(
            """
            SELECT * FROM leagues
            WHERE is_active = 1
            ORDER BY priority ASC, name ASC
            """
        )
        return cursor.fetchall()

    def inserer_ligues_principales(self) -> None:
        """
        Insère les 6 grandes ligues européennes
        avec leurs IDs FootyStats corrects.
        """
        from backend.core.constants import MAJOR_LEAGUE_IDS

        ligues = [
            {
                "footystats_id": 1625,
                "name": "Premier League",
                "country": "England",
                "tier": 1,
                "group_type": "major_european",
                "priority": 1,
            },
            {
                "footystats_id": 1869,
                "name": "La Liga",
                "country": "Spain",
                "tier": 1,
                "group_type": "major_european",
                "priority": 1,
            },
            {
                "footystats_id": 1854,
                "name": "Serie A",
                "country": "Italy",
                "tier": 1,
                "group_type": "major_european",
                "priority": 1,
            },
            {
                "footystats_id": 1867,
                "name": "Bundesliga",
                "country": "Germany",
                "tier": 1,
                "group_type": "major_european",
                "priority": 1,
            },
            {
                "footystats_id": 1871,
                "name": "Ligue 1",
                "country": "France",
                "tier": 1,
                "group_type": "major_european",
                "priority": 1,
            },
            {
                "footystats_id": 1005,
                "name": "Champions League",
                "country": "Europe",
                "tier": 1,
                "group_type": "major_european",
                "priority": 1,
            },
        ]

        for ligue in ligues:
            self.sauvegarder(ligue)

        logger.info_ctx(
            "Ligues principales insérées",
            context={"count": len(ligues)},
        )
