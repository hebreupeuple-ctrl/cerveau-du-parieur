"""
Pipeline principal de calcul des features.
Orchestre le calcul de toutes les features pour un match.
"""

import sqlite3
import time
from typing import Optional
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion

logger = get_logger(__name__)


class FeaturePipeline:
    """
    Calcule toutes les features pour un match donné.
    Respecte strictement le max_time pour éviter le data leakage.
    """

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()
        self._colonnes_match_features = None

    def calculer_features_match(
        self,
        match_id: int,
        match_timestamp: int,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        game_week: int = None,
    ) -> Optional[dict]:
        """
        Calcule toutes les features pour un match.
        Le max_time est fixé à 1 heure avant le coup d'envoi.
        """
        max_time = match_timestamp - 3600

        try:
            from backend.features.groups.forme import calculer_features_forme
            from backend.features.groups.h2h import calculer_features_h2h
            from backend.features.groups.contexte import calculer_features_contexte
            from backend.features.groups.ligue import calculer_features_ligue
            from backend.features.groups.classement import calculer_features_classement
            from backend.features.groups.shots_corners import calculer_features_shots_corners
            from backend.features.groups.arbitre import calculer_features_arbitre

            features = {"match_id": match_id, "max_time_used": max_time}

            # Groupe 1 — Forme récente
            forme_home = calculer_features_forme(
                conn=self.conn,
                team_id=home_team_id,
                max_time=max_time,
                domicile=True,
            )
            forme_away = calculer_features_forme(
                conn=self.conn,
                team_id=away_team_id,
                max_time=max_time,
                domicile=False,
            )

            for k, v in forme_home.items():
                features[f"home_{k}"] = v
            for k, v in forme_away.items():
                features[f"away_{k}"] = v

            # Groupe 6 — H2H
            h2h = calculer_features_h2h(
                conn=self.conn,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                max_time=max_time,
            )
            features.update(h2h)

            # Groupe 7 — Contexte
            contexte = calculer_features_contexte(
                conn=self.conn,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_timestamp=match_timestamp,
                game_week=game_week,
                league_id=league_id,
            )
            features.update(contexte)

            # Groupe 8 — Ligue
            ligue = calculer_features_ligue(
                conn=self.conn,
                league_id=league_id,
                max_time=max_time,
            )
            features.update(ligue)

            # Groupe 5 — Classement
            classement = calculer_features_classement(
                conn=self.conn,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                league_id=league_id,
                max_time=max_time,
            )
            features.update(classement)

            # Groupe 9 — Tirs, corners, possession, mi-temps, fatigue
            sc_home = calculer_features_shots_corners(
                conn=self.conn,
                team_id=home_team_id,
                max_time=max_time,
            )
            sc_away = calculer_features_shots_corners(
                conn=self.conn,
                team_id=away_team_id,
                max_time=max_time,
            )
            for k, v in sc_home.items():
                features[f"home_{k}"] = v
            for k, v in sc_away.items():
                features[f"away_{k}"] = v

            # Groupe 10 — Arbitre
            arbitre = calculer_features_arbitre(
                conn=self.conn,
                match_id=match_id,
                max_time=max_time,
            )
            features.update(arbitre)

            return features

        except Exception as e:
            logger.error_ctx(
                "Erreur calcul features",
                context={
                    "match_id": match_id,
                    "erreur": str(e),
                },
            )
            return None

    def sauvegarder_features(self, features: dict) -> bool:
        """
        Sauvegarde les features calculées dans la base.
        """
        return self._sauvegarder_features(features, commit=True)

    def invalider_cache_colonnes(self) -> None:
        """Invalide le cache des colonnes (à appeler après une migration)."""
        self._colonnes_match_features = None

    def _sauvegarder_features(
        self,
        features: dict,
        commit: bool,
    ) -> bool:
        """
        Sauvegarde les features calculées dans la base.
        """
        try:
            colonnes_valides = self._obtenir_colonnes_match_features()
            colonnes = [
                k for k in features.keys()
                if k in colonnes_valides
            ]

            # Log les features calculées mais absentes du schéma
            ignorees = [
                k for k in features.keys()
                if k not in colonnes_valides
                and k not in ("match_id", "max_time_used")
            ]
            if ignorees:
                logger.warning_ctx(
                    "Features ignorées : colonnes absentes de match_features",
                    context={
                        "match_id": features.get("match_id"),
                        "colonnes_manquantes": ignorees,
                    },
                )

            if not colonnes:
                return False

            valeurs = [features[k] for k in colonnes]
            placeholders = ", ".join(["?" for _ in colonnes])
            cols_str = ", ".join(colonnes)

            self.conn.execute(
                f"""
                INSERT OR REPLACE INTO match_features
                ({cols_str})
                VALUES ({placeholders})
                """,
                valeurs,
            )
            if commit:
                self.conn.commit()
            return True

        except Exception as e:
            logger.error_ctx(
                "Erreur sauvegarde features",
                context={
                    "match_id": features.get("match_id"),
                    "erreur": str(e),
                },
            )
            return False

    def _obtenir_colonnes_match_features(self) -> set[str]:
        if self._colonnes_match_features is None:
            cursor = self.conn.execute(
                "PRAGMA table_info(match_features)"
            )
            self._colonnes_match_features = {
                row["name"] for row in cursor.fetchall()
            }
        return self._colonnes_match_features

    def calculer_et_sauvegarder(
        self,
        match_id: int,
        match_timestamp: int,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        game_week: int = None,
        commit: bool = True,
    ) -> bool:
        """
        Calcule et sauvegarde les features en une seule opération.
        """
        features = self.calculer_features_match(
            match_id=match_id,
            match_timestamp=match_timestamp,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            league_id=league_id,
            game_week=game_week,
        )

        if features is None:
            return False

        return self._sauvegarder_features(features, commit=commit)
