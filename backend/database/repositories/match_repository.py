"""
Repository pour les matchs.
"""

import sqlite3
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion

logger = get_logger(__name__)


class MatchRepository:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()

    def sauvegarder(
        self,
        match: dict,
        season_id: int,
        league_id: int,
        home_team_id: int,
        away_team_id: int,
    ) -> Optional[int]:
        """
        Insère un match ou met à jour son statut.
        Retourne l'ID du match.
        """
        existant = self.trouver_par_footystats_id(
            match["footystats_id"]
        )

        if existant:
            if match.get("status") == "complete" and existant["status"] != "complete":
                self.conn.execute(
                    """
                    UPDATE matches SET
                        status = ?,
                        home_goals = ?,
                        away_goals = ?,
                        home_goals_ht = ?,
                        away_goals_ht = ?,
                        total_goals = ?,
                        result_1x2 = ?,
                        over15 = ?,
                        over25 = ?,
                        over35 = ?,
                        over45 = ?,
                        btts = ?,
                        home_xg = ?,
                        away_xg = ?,
                        home_shots = ?,
                        away_shots = ?,
                        home_shots_on_target = ?,
                        away_shots_on_target = ?,
                        home_corners = ?,
                        away_corners = ?,
                        home_yellow_cards = ?,
                        away_yellow_cards = ?,
                        home_red_cards = ?,
                        away_red_cards = ?,
                        home_possession = ?,
                        away_possession = ?,
                        updated_at = datetime('now')
                    WHERE footystats_id = ?
                    """,
                    (
                        match.get("status"),
                        match.get("home_goals"),
                        match.get("away_goals"),
                        match.get("home_goals_ht"),
                        match.get("away_goals_ht"),
                        match.get("total_goals"),
                        match.get("result_1x2"),
                        match.get("over15"),
                        match.get("over25"),
                        match.get("over35"),
                        match.get("over45"),
                        match.get("btts"),
                        match.get("home_xg"),
                        match.get("away_xg"),
                        match.get("home_shots"),
                        match.get("away_shots"),
                        match.get("home_shots_on_target"),
                        match.get("away_shots_on_target"),
                        match.get("home_corners"),
                        match.get("away_corners"),
                        match.get("home_yellow_cards"),
                        match.get("away_yellow_cards"),
                        match.get("home_red_cards"),
                        match.get("away_red_cards"),
                        match.get("home_possession"),
                        match.get("away_possession"),
                        match["footystats_id"],
                    ),
                )
                self.conn.commit()
            return existant["id"]

        try:
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO matches (
                    footystats_id, season_id, league_id,
                    home_team_id, away_team_id,
                    match_date, match_timestamp, game_week,
                    status, home_goals, away_goals,
                    home_goals_ht, away_goals_ht,
                    total_goals, result_1x2,
                    over15, over25, over35, over45, btts,
                    home_xg, away_xg,
                    home_shots, away_shots,
                    home_shots_on_target, away_shots_on_target,
                    home_corners, away_corners,
                    home_yellow_cards, away_yellow_cards,
                    home_red_cards, away_red_cards,
                    home_possession, away_possession,
                    competition_type
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    match["footystats_id"],
                    season_id,
                    league_id,
                    home_team_id,
                    away_team_id,
                    match.get("match_date"),
                    match.get("match_timestamp"),
                    match.get("game_week"),
                    match.get("status", "upcoming"),
                    match.get("home_goals"),
                    match.get("away_goals"),
                    match.get("home_goals_ht"),
                    match.get("away_goals_ht"),
                    match.get("total_goals"),
                    match.get("result_1x2"),
                    match.get("over15"),
                    match.get("over25"),
                    match.get("over35"),
                    match.get("over45"),
                    match.get("btts"),
                    match.get("home_xg"),
                    match.get("away_xg"),
                    match.get("home_shots"),
                    match.get("away_shots"),
                    match.get("home_shots_on_target"),
                    match.get("away_shots_on_target"),
                    match.get("home_corners"),
                    match.get("away_corners"),
                    match.get("home_yellow_cards"),
                    match.get("away_yellow_cards"),
                    match.get("home_red_cards"),
                    match.get("away_red_cards"),
                    match.get("home_possession"),
                    match.get("away_possession"),
                    match.get("competition_type", "league"),
                ),
            )
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error_ctx(
                "Erreur insertion match",
                context={
                    "footystats_id": match.get("footystats_id"),
                    "erreur": str(e),
                },
            )
            return None

    def trouver_par_footystats_id(
        self, footystats_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = self.conn.execute(
            "SELECT * FROM matches WHERE footystats_id = ?",
            (footystats_id,),
        )
        return cursor.fetchone()

    def trouver_par_id(
        self, match_id: int
    ) -> Optional[sqlite3.Row]:
        cursor = self.conn.execute(
            "SELECT * FROM matches WHERE id = ?",
            (match_id,),
        )
        return cursor.fetchone()

    def lister_matchs_a_venir(
        self,
        heures: int = 48,
        league_id: int = None,
    ) -> list:
        """
        Liste les matchs à venir dans les prochaines heures.
        """
        import time
        maintenant = int(time.time())
        limite = maintenant + (heures * 3600)

        if league_id:
            cursor = self.conn.execute(
                """
                SELECT * FROM matches
                WHERE status = 'upcoming'
                AND match_timestamp BETWEEN ? AND ?
                AND league_id = ?
                ORDER BY match_timestamp ASC
                """,
                (maintenant, limite, league_id),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM matches
                WHERE status = 'upcoming'
                AND match_timestamp BETWEEN ? AND ?
                ORDER BY match_timestamp ASC
                """,
                (maintenant, limite),
            )
        return cursor.fetchall()

    def lister_matchs_termines_sans_resultat(self) -> list:
        """
        Liste les matchs dont le timestamp est passé
        mais qui sont encore en statut upcoming.
        Utilisé pour détecter les résultats manquants.
        """
        import time
        maintenant = int(time.time())

        cursor = self.conn.execute(
            """
            SELECT * FROM matches
            WHERE status = 'upcoming'
            AND match_timestamp < ?
            ORDER BY match_timestamp DESC
            LIMIT 50
            """,
            (maintenant - 7200,),
        )
        return cursor.fetchall()

    def compter_par_ligue(self, league_id: int) -> dict:
        """
        Compte les matchs par statut pour une ligue.
        """
        cursor = self.conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM matches
            WHERE league_id = ?
            GROUP BY status
            """,
            (league_id,),
        )
        return {row["status"]: row["count"] for row in cursor.fetchall()}
