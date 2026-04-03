"""
Endpoints systeme.
"""

import asyncio
from datetime import datetime, timezone
import sqlite3
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.api.dependencies import get_current_admin_user, get_current_user, get_db
from backend.core.logging import get_logger
from backend.scheduler.locks import DistributedJobLockService

router = APIRouter()
logger = get_logger(__name__)
manual_system_lock = asyncio.Lock()
SYSTEM_PIPELINE_RESOURCE = "system_pipeline"


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/status")
async def status(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    from backend.scheduler.tasks.automation import obtenir_resume_features_historiques

    # Statistiques DB de base
    total_matchs    = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    total_ligues    = conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
    ligues_actives  = conn.execute("SELECT COUNT(*) FROM leagues WHERE is_active=1").fetchone()[0]
    matchs_a_venir  = conn.execute("SELECT COUNT(*) FROM matches WHERE status='upcoming'").fetchone()[0]
    matchs_complets = conn.execute("SELECT COUNT(*) FROM matches WHERE status='complete'").fetchone()[0]
    total_features  = conn.execute("SELECT COUNT(*) FROM match_features").fetchone()[0]
    total_odds      = conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0]

    # Qualité données HT
    ht_avec = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE status='complete' AND home_goals_ht IS NOT NULL"
    ).fetchone()[0]
    ht_pct = round(ht_avec / matchs_complets * 100, 1) if matchs_complets else 0

    # Pronostics par statut
    pronos = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) as n FROM pronostics GROUP BY status"
    ).fetchall():
        pronos[row["status"]] = row["n"]

    # Modèle ML actif
    modele = conn.execute(
        """SELECT version, trained_at, total_matches_trained,
                  brier_score_over25, auc_roc_over25
           FROM model_versions WHERE is_active=1 LIMIT 1"""
    ).fetchone()
    modele_data = dict(modele) if modele else {}

    # Jobs scheduler — 20 derniers (nettoyage des faux 'running' > 2h)
    conn.execute("""
        UPDATE scheduler_jobs SET status='failed', error_message='Interrompu (app restart)'
        WHERE status='running'
        AND started_at < datetime('now', '-2 hours')
    """)
    conn.commit()

    jobs = conn.execute(
        """SELECT job_name, status, started_at, completed_at,
                  execution_time_ms, error_message, result_summary_json
           FROM scheduler_jobs
           ORDER BY started_at DESC LIMIT 30"""
    ).fetchall()
    jobs_list = [dict(j) for j in jobs]

    historical_features = obtenir_resume_features_historiques(conn)

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "system_mode": "active",
                "api_status": "operational",
                "db": {
                    "total_ligues": total_ligues,
                    "ligues_actives": ligues_actives,
                    "total_matchs": total_matchs,
                    "matchs_a_venir": matchs_a_venir,
                    "matchs_complets": matchs_complets,
                    "total_features": total_features,
                    "total_odds": total_odds,
                    "ht_coverage_pct": ht_pct,
                    "ht_avec_donnees": ht_avec,
                },
                "pronostics": pronos,
                "modele": modele_data,
                "features_historiques": historical_features,
                "jobs": jobs_list,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
    )


@router.post("/manual-league-sync")
async def manual_league_sync(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Synchronise le catalogue des ligues puis déclenche
    automatiquement le pipeline système si le catalogue change.
    """
    from backend.scheduler.tasks.automation import (
        synchroniser_catalogue_et_automatiser_si_necessaire,
    )

    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    logger.info_ctx(
        "Synchronisation catalogue ligues demandee",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultat = await synchroniser_catalogue_et_automatiser_si_necessaire(
                user_ids=[current_user["id"]],
                max_pronostics=10,
            )
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    logger.info_ctx(
        "Synchronisation catalogue ligues terminee",
        context={
            "user_id": current_user["id"],
            "catalogue_changed": resultat.get("sync", {}).get(
                "catalogue_changed"
            ),
            "total_footystats": resultat.get("sync", {}).get("sync_ligues", {}).get(
                "total_footystats"
            ),
            "saisons_collectees": resultat.get("sync", {}).get(
                "saisons_collectees"
            ),
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": resultat,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )


@router.post("/manual-sync")
async def manual_sync(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Déclenche une synchronisation légère à la demande :
    - resynchronisation des ligues actives du package
    - rafraîchissement des matchs du jour
    - collecte des cotes des prochaines 48h
    - régénération des pronostics pending de l'utilisateur
    """
    from backend.scheduler.tasks.automation import (
        rafraichir_matchs_cotes_et_pronostics,
        synchroniser_catalogue,
    )

    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    logger.info_ctx(
        "Synchronisation manuelle demandee",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            sync_ligues = await synchroniser_catalogue()
            refresh = await rafraichir_matchs_cotes_et_pronostics(
                heures=48,
                user_ids=[current_user["id"]],
                max_pronostics=10,
                replace_pending=True,
            )
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )
    inserted = refresh["pronostics"]["inserted"]

    logger.info_ctx(
        "Synchronisation manuelle terminee",
        context={
            "user_id": current_user["id"],
            "pronostics_inserted": inserted,
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "sync_ligues": sync_ligues,
                "matchs_du_jour": refresh["matchs_du_jour"],
                "cotes": refresh["cotes"],
                "features": refresh["features"],
                "pronostics_generated": refresh["pronostics"]["inserted"],
                "pronostics_inserted": inserted,
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )


@router.post("/manual-feature-backfill")
async def manual_feature_backfill(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Déclenche un lot manuel de backfill des features historiques.
    """
    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    from backend.scheduler.tasks.automation import (
        backfill_features_historiques,
    )

    logger.info_ctx(
        "Backfill historique manuel demande",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultat = await backfill_features_historiques()
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    logger.info_ctx(
        "Backfill historique manuel termine",
        context={
            "user_id": current_user["id"],
            "processed": resultat.get("processed", 0),
            "remaining": resultat.get("after", {}).get(
                "features_historiques_manquantes",
            ),
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": resultat,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )


@router.post("/auto-resolve-pronostics")
async def auto_resolve_pronostics(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Résout automatiquement tous les pronostics placés dont le match est terminé
    et ignore les pronostics pending non placés sur matchs joués.
    """
    from backend.scheduler.tasks.automation import auto_resoudre_pronostics_termines

    logger.info_ctx(
        "Auto-résolution pronostics demandée",
        context={"user_id": current_user["id"]},
    )

    resultat = await auto_resoudre_pronostics_termines()

    return JSONResponse(
        content={
            "success": True,
            "data": resultat,
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        }
    )


@router.post("/pipeline-complet")
async def pipeline_complet(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Pipeline complet toutes ligues :
    1. Sync catalogue ligues
    2. Auto-résolution pronostics matchs terminés
    3. Backfill features historiques (jusqu'à 20 lots)
    4. Réentraînement modèle
    5. Rafraîchissement matchs + cotes + pronostics (72h)
    """
    from backend.scheduler.tasks.automation import pipeline_complet_toutes_ligues

    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
            },
        )

    logger.info_ctx(
        "Pipeline complet toutes ligues demandé",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultat = await pipeline_complet_toutes_ligues(
                user_ids=None,   # tous les utilisateurs actifs
                max_pronostics=10,
                max_backfill_batches=20,
            )
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    logger.info_ctx(
        "Pipeline complet terminé",
        context={
            "user_id": current_user["id"],
            "resolved": resultat.get("resolution", {}).get("resolved", 0),
            "backfill_processed": resultat.get("backfill", {}).get("processed", 0),
            "pronostics_inserted": resultat.get("refresh", {}).get(
                "pronostics", {}
            ).get("inserted", 0),
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": resultat,
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        }
    )


@router.post("/manual-retrain")
async def manual_retrain(
    current_user: dict = Depends(get_current_admin_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Déclenche un réentraînement manuel du modèle actif.
    """
    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
        )

    from backend.scheduler.tasks.automation import entrainer_modele

    logger.info_ctx(
        "Entrainement manuel demande",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultats = await entrainer_modele()
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    version = conn.execute(
        """
        SELECT version, trained_at, brier_score_over25, auc_roc_over25
        FROM model_versions
        WHERE is_active = 1
        LIMIT 1
        """
    ).fetchone()

    logger.info_ctx(
        "Entrainement manuel termine",
        context={
            "user_id": current_user["id"],
            "markets": resultats.get("markets", []),
            "version": version["version"] if version else None,
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "trained": bool(resultats.get("markets")),
                "markets": resultats.get("markets", []),
                "metrics": resultats.get("metrics", {}),
                "model_health": {
                    "model_version": version["version"] if version else None,
                    "last_retrain": version["trained_at"] if version else None,
                    "brier_score": (
                        version["brier_score_over25"] if version else None
                    ),
                    "auc_roc": (
                        version["auc_roc_over25"] if version else None
                    ),
                },
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )


@router.post("/recalculate-features")
async def recalculate_features(
    current_user: dict = Depends(get_current_admin_user),
):
    """
    Recalcule les features pour les matchs dont les nouvelles colonnes
    sont NULL (après ajout de nouveaux feature groups ou migrations).
    Traite par lots de 2000 jusqu'à ce qu'il n'y ait plus rien à faire.
    """
    lock_service = DistributedJobLockService()
    lock_token = await asyncio.to_thread(
        lock_service.acquire,
        SYSTEM_PIPELINE_RESOURCE,
    )
    if not lock_token:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_PIPELINE_BUSY",
                    "message": "Un job système est déjà en cours",
                },
                "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
            },
        )

    logger.info_ctx(
        "Recalcul features forcé demandé",
        context={"user_id": current_user["id"]},
    )

    async with manual_system_lock:
        try:
            resultat = await asyncio.to_thread(_recalculate_features_sync)
        finally:
            await asyncio.to_thread(
                lock_service.release,
                SYSTEM_PIPELINE_RESOURCE,
                lock_token,
            )

    logger.info_ctx(
        "Recalcul features forcé terminé",
        context={
            "user_id": current_user["id"],
            "processed": resultat.get("processed", 0),
            "ok": resultat.get("ok", 0),
        },
    )

    return JSONResponse(
        content={
            "success": True,
            "data": resultat,
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        }
    )


def _recalculate_features_sync() -> dict:
    from backend.database.connection import obtenir_connexion as creer_connexion
    from backend.features.pipeline import FeaturePipeline

    conn = creer_connexion()
    try:
        pipeline = FeaturePipeline(conn)

        # Cible les matchs complets avec features existantes mais nouvelles colonnes NULL
        rows = conn.execute(
            """
            SELECT m.id, m.match_timestamp, m.home_team_id,
                   m.away_team_id, m.league_id, m.game_week
            FROM matches m
            JOIN match_features mf ON mf.match_id = m.id
            JOIN leagues l ON l.id = m.league_id
            WHERE m.status = 'complete'
            AND l.is_active = 1
            AND (
                mf.bk_has_odds IS NULL
                OR mf.home_yellow_cards_avg_5m IS NULL
            )
            ORDER BY m.match_timestamp DESC
            LIMIT 2000
            """,
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

            if index % 200 == 0:
                conn.commit()

        conn.commit()

        remaining = conn.execute(
            """
            SELECT COUNT(*) FROM matches m
            JOIN match_features mf ON mf.match_id = m.id
            JOIN leagues l ON l.id = m.league_id
            WHERE m.status = 'complete' AND l.is_active = 1
            AND (mf.bk_has_odds IS NULL OR mf.home_yellow_cards_avg_5m IS NULL)
            """
        ).fetchone()[0]

        return {
            "processed": len(rows),
            "ok": ok,
            "fail": fail,
            "remaining": remaining,
        }
    finally:
        conn.close()
