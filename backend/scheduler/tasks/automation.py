"""
Taches d'automatisation du systeme.
"""

import asyncio
import sqlite3
import time
from typing import Optional, Sequence

from backend.analysis.accumulateur import GenerateurPronostics
from backend.data.collector import DataCollector
from backend.data.sync import collecter_nouvelles_ligues, synchroniser_ligues
from backend.database.connection import creer_connexion
from backend.features.pipeline import FeaturePipeline
from backend.models.trainer import ModelTrainer
from backend.odds.collector import OddsCollector


async def synchroniser_catalogue() -> dict:
    """
    Synchronise les ligues du package et collecte les nouvelles ligues.
    """
    conn = creer_connexion()
    try:
        sync_ligues = await synchroniser_ligues(conn)
        nouvelles_ligues = await collecter_nouvelles_ligues(conn)
        return {
            "sync_ligues": sync_ligues,
            "nouvelles_ligues": len(nouvelles_ligues),
        }
    finally:
        conn.close()


async def rafraichir_matchs_cotes_et_pronostics(
    heures: int = 48,
    user_ids: Optional[Sequence[int]] = None,
    max_pronostics: int = 10,
) -> dict:
    """
    Rafraichit les matchs du jour, les cotes, les features
    puis les pronostics utilisateur.
    """
    conn = creer_connexion()
    try:
        data_collector = DataCollector(conn)
        try:
            matchs_du_jour = await data_collector.collecter_matchs_aujourdhui()
        finally:
            await data_collector.fermer()

        odds_collector = OddsCollector(conn)
        try:
            cotes = await odds_collector.collecter_cotes_matchs_a_venir(heures=heures)
        finally:
            await odds_collector.fermer()
    finally:
        conn.close()

    features = await asyncio.to_thread(
        calculer_features_matchs_a_venir,
        heures,
    )
    pronostics = await asyncio.to_thread(
        regenerer_pronostics,
        user_ids,
        max_pronostics,
    )

    return {
        "matchs_du_jour": matchs_du_jour,
        "cotes": cotes,
        "features": features,
        "pronostics": pronostics,
    }


def calculer_features_matchs_a_venir(heures: int = 48) -> dict:
    """
    Calcule et sauvegarde les features des matchs a venir.
    """
    conn = creer_connexion()
    try:
        pipeline = FeaturePipeline(conn)
        maintenant = int(time.time())
        limite = maintenant + (heures * 3600)

        rows = conn.execute(
            """
            SELECT id, match_timestamp, home_team_id,
                   away_team_id, league_id, game_week
            FROM matches
            WHERE status = 'upcoming'
            AND match_timestamp BETWEEN ? AND ?
            """,
            (maintenant, limite),
        ).fetchall()

        ok = 0
        fail = 0

        for match in rows:
            success = pipeline.calculer_et_sauvegarder(
                match_id=match["id"],
                match_timestamp=match["match_timestamp"],
                home_team_id=match["home_team_id"],
                away_team_id=match["away_team_id"],
                league_id=match["league_id"],
                game_week=match["game_week"],
            )
            if success:
                ok += 1
            else:
                fail += 1

        return {
            "total": len(rows),
            "ok": ok,
            "fail": fail,
        }
    finally:
        conn.close()


def regenerer_pronostics(
    user_ids: Optional[Sequence[int]] = None,
    max_pronostics: int = 10,
) -> dict:
    """
    Regenere les pronostics pending pour les utilisateurs actifs.
    """
    conn = creer_connexion()
    try:
        if user_ids:
            placeholders = ", ".join("?" for _ in user_ids)
            users = conn.execute(
                f"""
                SELECT * FROM users
                WHERE is_active = 1
                AND id IN ({placeholders})
                """,
                tuple(user_ids),
            ).fetchall()
        else:
            users = conn.execute(
                """
                SELECT * FROM users
                WHERE is_active = 1
                ORDER BY id ASC
                """
            ).fetchall()

        generateur = GenerateurPronostics(conn)
        total_inserted = 0
        by_user = {}

        for user in users:
            pronostics = generateur.generer_pronostics_du_jour(
                user_id=user["id"],
                bankroll=user["current_bankroll"],
                bankroll_initiale=user["initial_bankroll"],
                fraction_override=user["kelly_fraction"],
                max_pronostics=max_pronostics,
            )

            conn.execute(
                """
                DELETE FROM pronostics
                WHERE user_id = ?
                AND status = 'pending'
                """,
                (user["id"],),
            )

            inserted = 0
            for pronostic in pronostics:
                conn.execute(
                    """
                    INSERT INTO pronostics (
                        user_id, match_id, market,
                        model_probability, bookmaker_probability, probability_edge,
                        expected_value, reference_bookmaker, reference_odds,
                        confidence_score, kelly_fraction_used, kelly_raw,
                        recommended_stake, bankroll_at_recommendation, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        user["id"],
                        pronostic["match_id"],
                        pronostic["marche"],
                        pronostic["probabilite_modele"],
                        pronostic["probabilite_bookmaker"],
                        pronostic["edge"],
                        pronostic["ev"],
                        "footystats",
                        pronostic["cote"],
                        pronostic["confiance"],
                        pronostic["kelly_fraction"],
                        pronostic["kelly_brut"],
                        pronostic["mise_recommandee"],
                        user["current_bankroll"],
                    ),
                )
                inserted += 1

            total_inserted += inserted
            by_user[user["email"]] = inserted

        conn.commit()

        return {
            "users": len(users),
            "inserted": total_inserted,
            "by_user": by_user,
        }
    finally:
        conn.close()


async def entrainer_modele() -> dict:
    """
    Entraine l'ensemble ML en tache de fond.
    """
    return await asyncio.to_thread(_entrainer_modele_sync)


def _entrainer_modele_sync() -> dict:
    conn = creer_connexion()
    try:
        trainer = ModelTrainer(conn)
        resultats = trainer.entrainer_tous()
        return {
            "markets": list(resultats.keys()),
            "metrics": resultats,
        }
    finally:
        conn.close()
