"""
Taches d'automatisation du systeme.
"""

import asyncio
import glob
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

from backend.core.config import settings
from backend.analysis.accumulateur import GenerateurPronostics
from backend.data.collector import DataCollector
from backend.data.sync import collecter_nouvelles_ligues, synchroniser_ligues
from backend.database.connection import creer_connexion
from backend.features.pipeline import FeaturePipeline
from backend.models.trainer import ModelTrainer
from backend.odds.collector import OddsCollector

from backend.core.logging import get_logger
from backend.scheduler.locks import DistributedJobLockService

logger = get_logger(__name__)


async def sauvegarder_base_de_donnees() -> dict:
    """
    Copie cerveau.db dans BACKUP_DIR/cerveau_YYYYMMDD.db.
    Conserve les 7 sauvegardes les plus récentes.
    """
    backup_dir = settings.BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)

    source = settings.DATABASE_PATH
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    dest = os.path.join(backup_dir, f"cerveau_{date_str}.db")

    try:
        shutil.copy2(source, dest)
    except Exception as exc:
        logger.error_ctx(
            "Echec sauvegarde base de donnees",
            context={"dest": dest, "erreur": str(exc)},
        )
        return {"success": False, "error": str(exc)}

    # Conserver uniquement les 7 sauvegardes les plus récentes
    pattern = os.path.join(backup_dir, "cerveau_*.db")
    backups = sorted(glob.glob(pattern))
    for old in backups[:-7]:
        try:
            os.remove(old)
        except OSError:
            pass

    logger.info_ctx(
        "Sauvegarde base de donnees effectuee",
        context={"dest": dest, "backups_conserves": min(len(backups), 7)},
    )
    return {"success": True, "path": dest}


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

    # Verrou distribué : évite deux pipelines complets en parallèle
    # (ex: deux instances qui reçoivent catalogue_changed simultanément).
    lock_svc = DistributedJobLockService()
    token = lock_svc.acquire("pipeline_catalogue")
    if token is None:
        logger.warning_ctx(
            "Pipeline catalogue déjà en cours sur une autre instance, skip",
            context={},
        )
        return {
            "sync": sync,
            "pipeline_triggered": False,
            "reason": "locked_by_another_instance",
        }

    try:
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
    finally:
        lock_svc.release("pipeline_catalogue", token)

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

    # Résolution automatique des pronostics placed sur matchs terminés
    resolution = await auto_resoudre_pronostics_termines()

    features = await asyncio.to_thread(
        calculer_features_matchs_a_venir,
        heures,
    )

    # Ne pas générer les pronostics si le calcul des features a totalement échoué
    # (évite de produire des recommandations sur données obsolètes)
    features_ok = features.get("ok", 0) > 0 or features.get("total", 0) == 0
    if not features_ok:
        logger.warning_ctx(
            "Génération pronostics ignorée : aucune feature calculée avec succès",
            context={"features": features},
        )
        pronostics = {"users": 0, "inserted": 0, "skipped": True}
    else:
        pronostics = await asyncio.to_thread(
            regenerer_pronostics,
            user_ids,
            max_pronostics,
        )

    return {
        "matchs_du_jour": matchs_du_jour,
        "cotes": cotes,
        "resolution": resolution,
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
    Si la bankroll est tombée sous SUSPENSION_THRESHOLD, aucun pronostic
    n'est généré pour protéger la bankroll restante.
    """
    current_bankroll = user["current_bankroll"] or 0.0
    initial_bankroll = user["initial_bankroll"] or 1.0
    ratio_bankroll = current_bankroll / max(initial_bankroll, 1.0)

    if ratio_bankroll < settings.SUSPENSION_THRESHOLD:
        logger.warning_ctx(
            "Génération suspendue — bankroll sous le seuil de protection",
            context={
                "user_id": user["id"],
                "ratio_bankroll": round(ratio_bankroll, 4),
                "seuil": settings.SUSPENSION_THRESHOLD,
                "current_bankroll": current_bankroll,
                "initial_bankroll": initial_bankroll,
            },
        )
        return {
            "user_id": user["id"],
            "email": user["email"],
            "inserted": 0,
            "generated": 0,
            "suspended": True,
        }

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
            INSERT OR IGNORE INTO pronostics (
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



def _determiner_resultat_marche(
    marche: str,
    home_goals: int,
    away_goals: int,
    total_goals: int,
    home_goals_ht,
    away_goals_ht,
) -> str:
    """
    Détermine le résultat d'un marché donné à partir des buts du match.
    Retourne 'won', 'lost' ou 'void'.
    """
    hg = home_goals or 0
    ag = away_goals or 0
    tg = total_goals if total_goals is not None else (hg + ag)

    if marche == "over25":
        return "won" if tg > 2 else "lost"
    elif marche == "over15":
        return "won" if tg > 1 else "lost"
    elif marche == "over35":
        return "won" if tg > 3 else "lost"
    elif marche == "btts":
        return "won" if (hg > 0 and ag > 0) else "lost"
    elif marche == "over15_ht":
        if home_goals_ht is None or away_goals_ht is None:
            return "void"
        return "won" if (home_goals_ht + away_goals_ht) > 1 else "lost"
    elif marche == "1x2_home":
        return "won" if hg > ag else "lost"
    elif marche == "1x2_draw":
        return "won" if hg == ag else "lost"
    elif marche == "1x2_away":
        return "won" if ag > hg else "lost"
    # Marché inconnu → void
    return "void"


async def auto_resoudre_pronostics_termines() -> dict:
    """
    Résout automatiquement les pronostics dont le match est terminé :
    - 'placed' → résolution avec impact bankroll (won/lost/void)
    - 'pending' → marqué 'ignored' (jamais placé, match déjà joué)
    """
    return await asyncio.to_thread(_auto_resoudre_pronostics_sync)


def _auto_resoudre_pronostics_sync() -> dict:
    conn = creer_connexion()
    try:
        maintenant = int(time.time())
        resolved = 0
        ignored = 0
        erreurs = 0

        # ── 0. Marquer les matchs passés (> 2h) encore en 'upcoming' ────
        # Permet que la résolution des pronostics fonctionne même si
        # la collecte des résultats FootyStats est en retard.
        conn.execute(
            """
            UPDATE matches SET status = 'complete'
            WHERE status = 'upcoming'
            AND match_timestamp < ?
            """,
            (maintenant - 2 * 3600,),
        )
        conn.commit()

        # ── 1. Pronostics PLACED dont le match est terminé ──────────────
        placed_rows = conn.execute(
            """
            SELECT
                p.id, p.user_id, p.market, p.actual_stake, p.actual_odds,
                m.home_goals, m.away_goals, m.total_goals,
                m.home_goals_ht, m.away_goals_ht
            FROM pronostics p
            JOIN matches m ON p.match_id = m.id
            WHERE p.status = 'placed'
            AND m.status = 'complete'
            AND m.home_goals IS NOT NULL
            AND m.away_goals IS NOT NULL
            AND datetime(m.updated_at) > datetime(m.match_timestamp, 'unixepoch')
            """
        ).fetchall()

        for p in placed_rows:
            try:
                resultat = _determiner_resultat_marche(
                    marche=p["market"],
                    home_goals=p["home_goals"],
                    away_goals=p["away_goals"],
                    total_goals=p["total_goals"],
                    home_goals_ht=p["home_goals_ht"],
                    away_goals_ht=p["away_goals_ht"],
                )

                stake = p["actual_stake"] or 0.0
                odds = p["actual_odds"] or 1.0

                if resultat == "won":
                    profit = round(stake * (odds - 1.0), 2)
                    retour = round(stake + profit, 2)
                elif resultat == "lost":
                    profit = -stake
                    retour = 0.0
                else:  # void
                    profit = 0.0
                    retour = stake

                # Lire bankroll actuelle
                user_row = conn.execute(
                    "SELECT current_bankroll FROM users WHERE id = ?",
                    (p["user_id"],),
                ).fetchone()
                if not user_row:
                    continue

                bankroll_avant = user_row["current_bankroll"]
                nouvelle_bankroll = round(bankroll_avant + retour, 2)

                conn.execute(
                    """
                    UPDATE pronostics SET
                        status = ?,
                        actual_profit = ?,
                        resolved_at = datetime('now')
                    WHERE id = ?
                    """,
                    (resultat, profit, p["id"]),
                )
                conn.execute(
                    """
                    UPDATE users SET
                        current_bankroll = ?,
                        bankroll_updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (nouvelle_bankroll, p["user_id"]),
                )
                transaction_type = (
                    "bet_won" if resultat == "won"
                    else "bet_void" if resultat == "void"
                    else "bet_lost"
                )
                conn.execute(
                    """
                    INSERT INTO bankroll_transactions (
                        user_id, pronostic_id, transaction_type,
                        amount, balance_before, balance_after, reference_note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p["user_id"],
                        p["id"],
                        transaction_type,
                        retour,
                        bankroll_avant,
                        nouvelle_bankroll,
                        f"Auto-résolution {resultat} — {p['market']}",
                    ),
                )
                resolved += 1

            except Exception as e:
                erreurs += 1
                logger.error_ctx(
                    "Erreur auto-résolution pronostic placé",
                    context={"pronostic_id": p["id"], "erreur": str(e)},
                )

        # ── 2. Pronostics PENDING dont le match est déjà terminé ───────
        # Deux conditions OR : match marqué 'complete' OU timestamp dépassé
        # depuis plus de 2h (buffer pour la collecte des résultats).
        delai_expiration = maintenant - 2 * 3600
        cursor_ignore = conn.execute(
            """
            UPDATE pronostics
            SET status = 'ignored',
                ignored_at = datetime('now'),
                ignore_reason = 'match_termine_sans_placement'
            WHERE status = 'pending'
            AND match_id IN (
                SELECT id FROM matches
                WHERE status = 'complete'
                   OR match_timestamp < ?
            )
            """,
            (delai_expiration,),
        )
        ignored = cursor_ignore.rowcount

        conn.commit()

        # ── 3. Re-résolution des erreurs prématurées ─────────────────────
        # Si le match a été mis à jour par FootyStats APRÈS la résolution
        # initiale (ex: scores pré-match 0/0 utilisés par erreur), on
        # recalcule et on corrige le résultat + la bankroll.
        recorriges = 0
        recheck_rows = conn.execute(
            """
            SELECT
                p.id, p.user_id, p.market, p.status as old_status,
                p.actual_stake, p.actual_odds, p.actual_profit,
                m.home_goals, m.away_goals, m.total_goals,
                m.home_goals_ht, m.away_goals_ht
            FROM pronostics p
            JOIN matches m ON p.match_id = m.id
            WHERE p.status IN ('won', 'lost')
            AND p.resolved_at IS NOT NULL
            AND p.resolved_at > datetime('now', '-24 hours')
            AND m.home_goals IS NOT NULL
            AND m.away_goals IS NOT NULL
            AND datetime(m.updated_at) > datetime(p.resolved_at)
            """
        ).fetchall()

        for p in recheck_rows:
            try:
                new_result = _determiner_resultat_marche(
                    marche=p["market"],
                    home_goals=p["home_goals"],
                    away_goals=p["away_goals"],
                    total_goals=p["total_goals"],
                    home_goals_ht=p["home_goals_ht"],
                    away_goals_ht=p["away_goals_ht"],
                )

                if new_result == p["old_status"]:
                    continue  # Résultat inchangé

                stake = p["actual_stake"] or 0.0
                odds = p["actual_odds"] or 1.0
                old_profit = p["actual_profit"] or 0.0

                if new_result == "won":
                    new_profit = round(stake * (odds - 1.0), 2)
                elif new_result == "lost":
                    new_profit = -stake
                else:
                    new_profit = 0.0

                bankroll_delta = round(new_profit - old_profit, 2)

                conn.execute(
                    """
                    UPDATE pronostics SET
                        status = ?,
                        actual_profit = ?,
                        resolved_at = datetime('now')
                    WHERE id = ?
                    """,
                    (new_result, new_profit, p["id"]),
                )
                conn.execute(
                    """
                    UPDATE users SET
                        current_bankroll = round(current_bankroll + ?, 2),
                        bankroll_updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (bankroll_delta, p["user_id"]),
                )
                recorriges += 1
                logger.info_ctx(
                    "Pronostic re-résolu (scores mis à jour après résolution)",
                    context={
                        "pronostic_id": p["id"],
                        "marche": p["market"],
                        "ancien": p["old_status"],
                        "nouveau": new_result,
                        "delta_bankroll": bankroll_delta,
                    },
                )
            except Exception as e:
                logger.error_ctx(
                    "Erreur re-résolution pronostic",
                    context={"pronostic_id": p["id"], "erreur": str(e)},
                )

        if recorriges:
            conn.commit()

        logger.info_ctx(
            "Auto-résolution pronostics terminée",
            context={
                "resolved": resolved,
                "ignored": ignored,
                "recorriges": recorriges,
                "erreurs": erreurs,
            },
        )

        return {
            "resolved": resolved,
            "ignored": ignored,
            "recorriges": recorriges,
            "erreurs": erreurs,
        }
    finally:
        conn.close()


async def pipeline_complet_toutes_ligues(
    user_ids: Optional[Sequence[int]] = None,
    max_pronostics: int = 10,
    max_backfill_batches: int = 20,
) -> dict:
    """
    Pipeline complet :
    1. Synchronise TOUTES les ligues disponibles (force catalogue_changed)
    2. Auto-résout les pronostics des matchs terminés
    3. Backfill des features historiques (plusieurs lots)
    4. Réentraîne le modèle
    5. Rafraîchit les matchs, cotes et pronostics
    """
    # Étape 1 : sync catalogue
    sync = await synchroniser_catalogue()

    # Étape 2 : auto-résolution pronostics terminés
    resolution = await auto_resoudre_pronostics_termines()

    # Étape 3 : backfill features historiques (force plusieurs lots)
    backfill_processed = 0
    backfill_ok = 0
    backfill_fail = 0

    for _ in range(max_backfill_batches):
        res = await backfill_features_historiques()
        backfill_processed += res.get("processed", 0)
        backfill_ok += res.get("ok", 0)
        backfill_fail += res.get("fail", 0)
        remaining = res.get("after", {}).get("features_historiques_manquantes", 0)
        if res.get("processed", 0) == 0 or remaining == 0:
            break

    # Étape 4 : réentraînement modèle
    retrain = await entrainer_modele()

    # Étape 5 : rafraîchissement matchs + cotes + pronostics
    refresh = await rafraichir_matchs_cotes_et_pronostics(
        heures=72,
        user_ids=user_ids,
        max_pronostics=max_pronostics,
    )

    return {
        "sync": sync,
        "resolution": resolution,
        "backfill": {
            "processed": backfill_processed,
            "ok": backfill_ok,
            "fail": backfill_fail,
        },
        "retrain": retrain,
        "refresh": refresh,
    }
