"""
Taches d'automatisation du systeme.
"""

import asyncio
import sqlite3
import time
from typing import Optional, Sequence

from backend.core.config import settings
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
        saisons_collectees = await collecter_nouvelles_ligues(conn)
        return {
            "sync_ligues": sync_ligues,
            "catalogue_changed": bool(
                sync_ligues.get("catalogue_changed")
            ),
            "saisons_collectees": len(saisons_collectees),
            "nouvelles_ligues": len(saisons_collectees),
        }
    finally:
        conn.close()


async def synchroniser_catalogue_et_automatiser_si_necessaire(
    heures: int = 48,
    user_ids: Optional[Sequence[int]] = None,
    max_pronostics: int = 10,
    max_backfill_batches: Optional[int] = None,
) -> dict:
    """
    Synchronise le catalogue puis déclenche automatiquement
    backfill, réentraînement et rafraîchissement des pronostics
    si le catalogue a réellement changé.
    """
    sync = await synchroniser_catalogue()
    if not sync.get("catalogue_changed"):
        return {
            "sync": sync,
            "pipeline_triggered": False,
            "reason": "catalogue_unchanged",
        }

    batches_limit = (
        max_backfill_batches
        or settings.CATALOG_CHANGE_BACKFILL_MAX_BATCHES
    )
    backfill_batches = 0
    backfill_processed = 0
    backfill_ok = 0
    backfill_fail = 0
    remaining_backfill = None

    for _ in range(batches_limit):
        resultat_backfill = await backfill_features_historiques()
        backfill_batches += 1
        backfill_processed += resultat_backfill.get("processed", 0)
        backfill_ok += resultat_backfill.get("ok", 0)
        backfill_fail += resultat_backfill.get("fail", 0)
        remaining_backfill = resultat_backfill.get("after", {}).get(
            "features_historiques_manquantes"
        )

        if (
            resultat_backfill.get("processed", 0) == 0
            or remaining_backfill == 0
        ):
            break

    retrain = await entrainer_modele()
    refresh = await rafraichir_matchs_cotes_et_pronostics(
        heures=heures,
        user_ids=user_ids,
        max_pronostics=max_pronostics,
    )

    return {
        "sync": sync,
        "pipeline_triggered": True,
        "backfill": {
            "batches": backfill_batches,
            "processed": backfill_processed,
            "ok": backfill_ok,
            "fail": backfill_fail,
            "remaining": remaining_backfill,
            "complete": remaining_backfill == 0,
        },
        "retrain": {
            "trained": bool(retrain.get("markets")),
            **retrain,
        },
        "refresh": refresh,
    }


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
            resultat = generer_et_sauvegarder_pronostics_utilisateur(
                conn=conn,
                user=user,
                generateur=generateur,
                max_pronostics=max_pronostics,
                replace_pending=True,
                commit=False,
            )
            total_inserted += resultat["inserted"]
            by_user[user["email"]] = resultat["inserted"]

        conn.commit()

        return {
            "users": len(users),
            "inserted": total_inserted,
            "by_user": by_user,
        }
    finally:
        conn.close()


def generer_et_sauvegarder_pronostics_utilisateur(
    conn: sqlite3.Connection,
    user: sqlite3.Row | dict,
    generateur: Optional[GenerateurPronostics] = None,
    max_pronostics: int = 10,
    replace_pending: bool = True,
    commit: bool = False,
) -> dict:
    """
    Génère puis sauvegarde les pronostics pending d'un utilisateur.
    """
    generateur = generateur or GenerateurPronostics(conn)
    pronostics = generateur.generer_pronostics_du_jour(
        user_id=user["id"],
        bankroll=user["current_bankroll"],
        bankroll_initiale=user["initial_bankroll"],
        fraction_override=user["kelly_fraction"],
        max_pronostics=max_pronostics,
    )

    if replace_pending:
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

    if commit:
        conn.commit()

    return {
        "user_id": user["id"],
        "email": user["email"],
        "inserted": inserted,
        "generated": len(pronostics),
    }


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


def obtenir_resume_features_historiques(
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """
    Retourne l'état du backfill historique des features.
    """
    own_conn = conn is None
    conn = conn or creer_connexion()
    try:
        matches_complete = conn.execute(
            """
            SELECT COUNT(*)
            FROM matches m
            JOIN leagues l ON l.id = m.league_id
            WHERE m.status = 'complete'
            AND l.is_active = 1
            """
        ).fetchone()[0]

        features_historiques_calculees = conn.execute(
            """
            SELECT COUNT(*)
            FROM match_features mf
            JOIN matches m ON m.id = mf.match_id
            JOIN leagues l ON l.id = m.league_id
            WHERE m.status = 'complete'
            AND l.is_active = 1
            """
        ).fetchone()[0]

        features_historiques_manquantes = conn.execute(
            """
            SELECT COUNT(*)
            FROM matches m
            LEFT JOIN match_features mf ON mf.match_id = m.id
            JOIN leagues l ON l.id = m.league_id
            WHERE m.status = 'complete'
            AND l.is_active = 1
            AND mf.match_id IS NULL
            """
        ).fetchone()[0]

        coverage = round(
            (
                features_historiques_calculees
                / max(matches_complete, 1)
            ) * 100,
            2,
        ) if matches_complete > 0 else 0.0

        return {
            "matches_complete": matches_complete,
            "features_historiques_calculees": (
                features_historiques_calculees
            ),
            "features_historiques_manquantes": (
                features_historiques_manquantes
            ),
            "historical_backfill_coverage_pct": coverage,
        }
    finally:
        if own_conn:
            conn.close()


async def backfill_features_historiques(
    batch_size: Optional[int] = None,
) -> dict:
    """
    Backfill un lot de features historiques pour les matchs complets.
    """
    effective_batch_size = (
        batch_size
        or settings.HISTORICAL_FEATURE_BACKFILL_BATCH_SIZE
    )
    return await asyncio.to_thread(
        _backfill_features_historiques_sync,
        effective_batch_size,
    )


def _backfill_features_historiques_sync(
    batch_size: int,
) -> dict:
    conn = creer_connexion()
    try:
        before = obtenir_resume_features_historiques(conn)
        pipeline = FeaturePipeline(conn)

        rows = conn.execute(
            """
            SELECT m.id, m.match_timestamp, m.home_team_id,
                   m.away_team_id, m.league_id, m.game_week
            FROM matches m
            LEFT JOIN match_features mf ON mf.match_id = m.id
            JOIN leagues l ON l.id = m.league_id
            WHERE m.status = 'complete'
            AND l.is_active = 1
            AND mf.match_id IS NULL
            ORDER BY m.match_timestamp ASC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()

        ok = 0
        fail = 0

        for index, match in enumerate(rows, start=1):
            success = pipeline.calculer_et_sauvegarder(
                match_id=match["id"],
                match_timestamp=match["match_timestamp"],
                home_team_id=match["home_team_id"],
                away_team_id=match["away_team_id"],
                league_id=match["league_id"],
                game_week=match["game_week"],
                commit=False,
            )
            if success:
                ok += 1
            else:
                fail += 1

            if index % 100 == 0:
                conn.commit()

        conn.commit()
        after = obtenir_resume_features_historiques(conn)

        return {
            "batch_size": batch_size,
            "processed": len(rows),
            "ok": ok,
            "fail": fail,
            "before": before,
            "after": after,
        }
    finally:
        conn.close()
