"""
Repository pour les équipes.
"""

import sqlite3
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion

logger = get_logger(__name__)


class TeamRepository:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()

    def sauvegarder(self, equipe: dict) -> int:
        """
        Insère ou met à jour une équipe.
        Retourne l'ID de l'équipe.
        """
        existante = self.trouver_par_footystats_id(
            equipe["footystats_id"]
        )

        if existante:
            return existante["id"]

        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO teams (
                footystats_id, name, country
            ) VALUES (?, ?, ?)
            """,
            (
                equipe["footystats_id"],
                equipe["name"],
                equipe.get("country", "Unknown"),
            ),
        )
        self.conn.commit()

        if cursor.lastrowid:
            return cursor.lastrowid

        row = self.trouver_par_footystats_id(
            equipe["footystats_id"]
        )
        return row["id"] if row else None

    def trouver_par_footystats_id(
        self, footystats_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = self.conn.execute(
            "SELECT * FROM teams WHERE footystats_id = ?",
            (footystats_id,),
        )
        return cursor.fetchone()

    def trouver_par_id(
        self, team_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = self.conn.execute(
            "SELECT * FROM teams WHERE id = ?",
            (team_id,),
        )
        return cursor.fetchone()

    def mettre_a_jour_parametres_dc(
        self,
        team_id: int,
        attack_home: float,
        attack_away: float,
        defense_home: float,
        defense_away: float,
    ) -> None:
        """
        Met à jour les paramètres Dixon-Coles d'une équipe.
        """
        self.conn.execute(
            """
            UPDATE teams SET
                attack_strength_home = ?,
                attack_strength_away = ?,
                defense_strength_home = ?,
                defense_strength_away = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                attack_home,
                attack_away,
                defense_home,
                defense_away,
                team_id,
            ),
        )
        self.conn.commit()
