"""
Endpoints pronostics.
"""

import asyncio
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import sqlite3

from backend.api.dependencies import get_db, get_current_user
from backend.core.config import settings
from backend.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def reponse_succes(data: dict):
    return JSONResponse(content={
        "success": True,
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
    })


def _obtenir_scores_exacts(conn: sqlite3.Connection, match_id: int) -> list:
    """
    Retourne les 3 scores les plus probables selon Dixon-Coles.
    Utilise la score_matrix stockée dans le pronostic le plus récent du match.
    """
    import json
    row = conn.execute(
        """
        SELECT score_matrix FROM pronostics
        WHERE match_id = ? AND score_matrix IS NOT NULL
        ORDER BY recommended_at DESC LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if not row or not row["score_matrix"]:
        return []
    try:
        matrice = json.loads(row["score_matrix"])
        top = sorted(matrice.items(), key=lambda x: x[1], reverse=True)[:3]
        return [
            {"score": score, "probabilite": round(prob * 100, 1)}
            for score, prob in top
            if prob > 0.04  # minimum 4% pour être affiché
        ]
    except Exception:
        return []


def _charger_pronostics_pending(
    conn: sqlite3.Connection,
    user_id: int,
    maintenant: int,
    dans_48h: int,
):
    return conn.execute(
        """
        SELECT p.*,
               m.match_timestamp, m.home_team_id, m.away_team_id,
               t1.name as home_team, t2.name as away_team,
               l.name as league_name
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        JOIN leagues l ON m.league_id = l.id
        WHERE p.user_id = ?
        AND p.status = 'pending'
        AND m.match_timestamp BETWEEN ? AND ?
        ORDER BY p.confidence_score DESC
        """,
        (user_id, maintenant, dans_48h),
    ).fetchall()


@router.get("/today")
async def pronostics_du_jour(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    maintenant = int(time.time())
    # Fin du jour courant en heure de Paris (gère CET/CEST automatiquement)
    paris_tz = ZoneInfo("Europe/Paris")
    now_paris = datetime.now(paris_tz)
    fin_du_jour = int(
        now_paris.replace(hour=23, minute=59, second=59, microsecond=0).timestamp()
    )

    pronostics_db = _charger_pronostics_pending(
        conn,
        current_user["id"],
        maintenant,
        fin_du_jour,
    )

    if not pronostics_db:
        # Compte uniquement les pending/placed : si tous les pronostics ont été
        # placés/ignorés mais un nouveau match tombe dans la fenêtre, on doit
        # regénérer. Exclure won/lost/void/ignored qui ne bloquent pas la génération.
        existing_window_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM pronostics p
            JOIN matches m ON p.match_id = m.id
            WHERE p.user_id = ?
            AND p.status IN ('pending', 'placed')
            AND m.match_timestamp BETWEEN ? AND ?
            """,
            (current_user["id"], maintenant, fin_du_jour),
        ).fetchone()[0]

        if existing_window_count == 0:
            from backend.scheduler.tasks.automation import (
                generer_et_sauvegarder_pronostics_utilisateur,
            )

            user_row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (current_user["id"],),
            ).fetchone()

            # Vérification du seuil de suspension bankroll
            bankroll_ratio = (
                (user_row["current_bankroll"] or 0.0)
                / max(user_row["initial_bankroll"] or 1.0, 1.0)
                if user_row else 1.0
            )

            if user_row and bankroll_ratio >= settings.SUSPENSION_THRESHOLD:
                # Génération dans un thread pour ne pas bloquer la réponse HTTP
                from backend.database.connection import creer_connexion
                def _generer():
                    conn_bg = creer_connexion()
                    try:
                        user_bg = conn_bg.execute(
                            "SELECT * FROM users WHERE id = ?",
                            (user_row["id"],),
                        ).fetchone()
                        if user_bg:
                            generer_et_sauvegarder_pronostics_utilisateur(
                                conn=conn_bg,
                                user=user_bg,
                                max_pronostics=10,
                                replace_pending=True,
                                commit=True,
                            )
                    finally:
                        conn_bg.close()

                async def _generer_avec_gestion_erreur():
                    try:
                        await asyncio.to_thread(_generer)
                    except Exception as exc:
                        logger.error_ctx(
                            "Erreur génération pronostics arrière-plan",
                            context={"user_id": current_user["id"], "erreur": str(exc)},
                        )

                asyncio.create_task(_generer_avec_gestion_erreur())
                logger.info_ctx(
                    "Génération pronostics lancée en arrière-plan",
                    context={"user_id": current_user["id"]},
                )

    MARKET_LABELS_TODAY = {
        "over15":    "Plus de 1.5 buts",
        "over25":    "Plus de 2.5 buts",
        "over35":    "Plus de 3.5 buts",
        "over45":    "Plus de 4.5 buts",
        "btts":      "Les deux équipes marquent",
        "over15_ht": "Plus de 1.5 buts (MT)",
        "1x2_home":  "Victoire domicile",
        "1x2_draw":  "Match nul",
        "1x2_away":  "Victoire extérieur",
        "1x2_ht_home": "Victoire domicile à la mi-temps",
        "1x2_ht_draw": "Nul à la mi-temps",
        "1x2_ht_away": "Victoire extérieur à la mi-temps",
        "under25":   "Moins de 2.5 buts",
        "ng":        "Aucune équipe ne marque",
        "dc_1x":     "Double chance 1X",
        "dc_x2":     "Double chance X2",
        "gg_over25": "GG & Plus de 2.5 buts",
    }

    # Marchés considérés comme "SAFE" (probabilité élevée, cote basse)
    MARCHES_SAFE = {"over15", "under25", "dc_1x", "dc_x2"}
    # Marchés considérés comme "PRÉCISION" (combinés ou dérivés spécifiques)
    MARCHES_PRECISION = {"gg_over25", "1x2_ht_home", "1x2_ht_draw", "1x2_ht_away"}

    pronostics_formatted = []
    for p in pronostics_db:
        pronostics_formatted.append({
            "id": p["id"],
            "match": {
                "id": p["match_id"],
                "home_team": p["home_team"],
                "away_team": p["away_team"],
                "league": p["league_name"],
                "kickoff_timestamp": p["match_timestamp"],
            },
            "market": p["market"],
            "market_label": MARKET_LABELS_TODAY.get(p["market"], p["market"]),
            "reference_bookmaker": p["reference_bookmaker"],
            "reference_odds": p["reference_odds"],
            "model_probability": p["model_probability"],
            "bookmaker_probability": p["bookmaker_probability"],
            "probability_edge": p["probability_edge"],
            "expected_value": p["expected_value"],
            "confidence_score": p["confidence_score"],
            "recommended_stake": p["recommended_stake"],
            "potential_gain": round(p["recommended_stake"] * (p["reference_odds"] - 1), 2),
            "status": p["status"],
        })

    # ── Groupement en fiches SAFE / VALEUR / PRÉCISION par match ──────────
    fiches_par_match = {}
    for p in pronostics_formatted:
        mid = p["match"]["id"]
        if mid not in fiches_par_match:
            fiches_par_match[mid] = []
        fiches_par_match[mid].append(p)

    fiches = []
    for mid, pronos in fiches_par_match.items():
        match_info = pronos[0]["match"]

        # Score exact depuis Dixon-Coles (top 3 scores les plus probables)
        exact_scores = _obtenir_scores_exacts(conn, mid)

        # SAFE : marché "sûr" avec confidence maximale
        safe_candidates = [p for p in pronos if p["market"] in MARCHES_SAFE]
        safe = (
            max(safe_candidates, key=lambda x: x["confidence_score"])
            if safe_candidates
            else max(pronos, key=lambda x: x["confidence_score"])
        )

        # VALEUR : meilleur EV, différent du SAFE
        valeur_candidates = [p for p in pronos if p["id"] != safe["id"]]
        valeur = (
            max(valeur_candidates, key=lambda x: x["expected_value"])
            if valeur_candidates else None
        )

        # PRÉCISION : marché combiné/mi-temps, différent des deux autres
        used_ids = {safe["id"]} | ({valeur["id"]} if valeur else set())
        precision_candidates = [
            p for p in pronos
            if p["id"] not in used_ids and p["market"] in MARCHES_PRECISION
        ]
        # Si pas de marché précision dédié, prendre le troisième meilleur EV
        if not precision_candidates:
            precision_candidates = [p for p in pronos if p["id"] not in used_ids]
        precision = (
            max(precision_candidates, key=lambda x: x["expected_value"])
            if precision_candidates else None
        )

        fiches.append({
            "match": match_info,
            "safe": safe,
            "valeur": valeur,
            "precision": precision,
            "exact_scores": exact_scores,
            "all": pronos,
        })

    # Trier les fiches par kickoff
    fiches.sort(key=lambda f: f["match"]["kickoff_timestamp"])

    prochain_match = None
    if not pronostics_formatted:
        row = conn.execute(
            """
            SELECT m.match_timestamp, t1.name AS home, t2.name AS away
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE m.status = 'upcoming' AND m.match_timestamp > ?
            ORDER BY m.match_timestamp ASC
            LIMIT 1
            """,
            (maintenant,),
        ).fetchone()
        if row:
            prochain_match = {
                "home": row["home"],
                "away": row["away"],
                "timestamp": row["match_timestamp"],
            }

    # Variations bankroll réelles depuis les transactions
    bankroll_stats = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE
                WHEN date(created_at) = date('now', 'localtime')
                AND transaction_type IN ('bet_won', 'bet_lost', 'bet_void')
                THEN amount ELSE 0 END), 0) as today_change,
            COALESCE(SUM(CASE
                WHEN created_at >= datetime('now', '-7 days')
                AND transaction_type IN ('bet_won', 'bet_lost', 'bet_void')
                THEN amount ELSE 0 END), 0) as week_change
        FROM bankroll_transactions
        WHERE user_id = ?
        """,
        (current_user["id"],),
    ).fetchone()

    today_change = round(bankroll_stats["today_change"], 2)
    week_change = round(bankroll_stats["week_change"], 2)
    initial = current_user["initial_bankroll"] or 1.0
    week_change_pct = round(week_change / initial * 100, 2)

    return reponse_succes({
        "system_mode": current_user["system_mode"],
        "pronostics": pronostics_formatted,
        "fiches": fiches,
        "prochain_match": prochain_match,
        "combine_recommendation": None,
        "bankroll_summary": {
            "current": current_user["current_bankroll"],
            "today_change": today_change,
            "week_change": week_change,
            "week_change_pct": week_change_pct,
        }
    })


class PlaceRequest(BaseModel):
    actual_stake: float = Field(gt=0)
    actual_odds: float = Field(gt=1.0)


@router.post("/{pronostic_id}/place")
async def placer_pari(
    pronostic_id: int,
    req: PlaceRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        conn.execute("BEGIN IMMEDIATE")

        pronostic = conn.execute(
            "SELECT * FROM pronostics WHERE id = ? AND user_id = ?",
            (pronostic_id, current_user["id"]),
        ).fetchone()

        if not pronostic:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Pronostic introuvable")

        if pronostic["status"] != "pending":
            conn.rollback()
            raise HTTPException(status_code=409, detail="Pari déjà placé ou ignoré")

        match = conn.execute(
            "SELECT match_timestamp FROM matches WHERE id = ?",
            (pronostic["match_id"],),
        ).fetchone()

        if match and match["match_timestamp"] < int(time.time()):
            conn.rollback()
            raise HTTPException(status_code=409, detail="Le match a déjà commencé")

        user_row = conn.execute(
            "SELECT current_bankroll FROM users WHERE id = ?",
            (current_user["id"],),
        ).fetchone()
        bankroll_avant = user_row["current_bankroll"] if user_row else 0

        if req.actual_stake < settings.MIN_STAKE:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Mise minimale: {settings.MIN_STAKE}",
            )

        if req.actual_stake > bankroll_avant:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="Bankroll insuffisante",
            )

        nouvelle_bankroll = round(bankroll_avant - req.actual_stake, 2)

        conn.execute(
            """
            UPDATE pronostics SET
                status = 'placed',
                actual_stake = ?,
                actual_odds = ?,
                placed_at = datetime('now')
            WHERE id = ?
            """,
            (req.actual_stake, req.actual_odds, pronostic_id),
        )

        conn.execute(
            """
            UPDATE users SET
                current_bankroll = ?,
                bankroll_updated_at = datetime('now')
            WHERE id = ?
            """,
            (nouvelle_bankroll, current_user["id"]),
        )

        conn.execute(
            """
            INSERT INTO bankroll_transactions (
                user_id, pronostic_id, transaction_type,
                amount, balance_before, balance_after, reference_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_user["id"],
                pronostic_id,
                "bet_placed",
                -req.actual_stake,
                bankroll_avant,
                nouvelle_bankroll,
                f"Pari place sur {pronostic['market']}",
            ),
        )

        conn.commit()
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise

    return reponse_succes({
        "pronostic_id": pronostic_id,
        "status": "placed",
        "actual_stake": req.actual_stake,
        "actual_odds": req.actual_odds,
        "new_bankroll": nouvelle_bankroll,
    })


class ResolveRequest(BaseModel):
    result: str = Field(..., pattern="^(won|lost|void)$")


@router.post("/{pronostic_id}/resolve")
async def resoudre_pronostic(
    pronostic_id: int,
    req: ResolveRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Résout un pronostic placé : enregistre le résultat (won/lost/void),
    calcule le profit réel et met à jour la bankroll.
    """
    try:
        conn.execute("BEGIN IMMEDIATE")

        pronostic = conn.execute(
            "SELECT * FROM pronostics WHERE id = ? AND user_id = ?",
            (pronostic_id, current_user["id"]),
        ).fetchone()

        if not pronostic:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Pronostic introuvable")

        if pronostic["status"] != "placed":
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="Seuls les paris placés peuvent être résolus",
            )

        stake = pronostic["actual_stake"] or 0.0
        odds = pronostic["actual_odds"] or 1.0

        if req.result == "won":
            profit = round(stake * (odds - 1.0), 2)
            retour = round(stake + profit, 2)
        elif req.result == "lost":
            profit = -stake
            retour = 0.0
        else:  # void
            profit = 0.0
            retour = stake

        user_row = conn.execute(
            "SELECT current_bankroll FROM users WHERE id = ?",
            (current_user["id"],),
        ).fetchone()
        bankroll_avant = user_row["current_bankroll"] if user_row else 0.0
        nouvelle_bankroll = round(bankroll_avant + retour, 2)

        conn.execute(
            """
            UPDATE pronostics SET
                status = ?,
                actual_profit = ?,
                resolved_at = datetime('now')
            WHERE id = ?
            """,
            (req.result, profit, pronostic_id),
        )

        conn.execute(
            """
            UPDATE users SET
                current_bankroll = ?,
                bankroll_updated_at = datetime('now')
            WHERE id = ?
            """,
            (nouvelle_bankroll, current_user["id"]),
        )

        transaction_type = (
            "bet_won" if req.result == "won"
            else "bet_void" if req.result == "void"
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
                current_user["id"],
                pronostic_id,
                transaction_type,
                retour,
                bankroll_avant,
                nouvelle_bankroll,
                f"Résolution {req.result} — {pronostic['market']}",
            ),
        )

        conn.commit()
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise

    return reponse_succes({
        "pronostic_id": pronostic_id,
        "result": req.result,
        "profit": profit,
        "new_bankroll": nouvelle_bankroll,
    })


@router.get("/history")
async def historique_pronostics(
    status: str = None,
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retourne l'historique des pronostics de l'utilisateur.
    status: filtre optionnel (won|lost|placed|pending|ignored|void)
    """
    MARKET_LABELS = {
        "over15":    "Plus de 1.5 buts",
        "over25":    "Plus de 2.5 buts",
        "over35":    "Plus de 3.5 buts",
        "over45":    "Plus de 4.5 buts",
        "btts":      "Les deux équipes marquent",
        "over15_ht": "Plus de 1.5 buts (MT)",
        "1x2_home":  "Victoire domicile",
        "1x2_draw":  "Match nul",
        "1x2_away":  "Victoire extérieur",
        "under25":   "Moins de 2.5 buts",
        "ng":        "Aucune équipe ne marque",
        "dc_1x":     "Double chance 1X",
        "dc_x2":     "Double chance X2",
        "gg_over25": "GG & Plus de 2.5 buts",
    }

    offset = (page - 1) * limit

    # Construire la clause WHERE selon le filtre
    if status == "en_cours":
        status_clause = "AND p.status IN ('pending', 'placed')"
        params_status = []
    elif status and status in ("won", "lost", "void", "placed", "pending", "ignored", "superseded"):
        status_clause = "AND p.status = ?"
        params_status = [status]
    else:
        status_clause = ""
        params_status = []

    params = [current_user["id"]] + params_status

    total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM pronostics p
        WHERE p.user_id = ?
        {status_clause}
        """,
        params,
    ).fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT p.*,
               m.match_timestamp, m.home_goals, m.away_goals, m.status as match_status,
               t1.name as home_team, t2.name as away_team,
               l.name as league_name
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        JOIN leagues l ON m.league_id = l.id
        WHERE p.user_id = ?
        {status_clause}
        ORDER BY p.recommended_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    # Stats globales (tous statuts confondus)
    stats = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN p.status = 'won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN p.status = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN p.status IN ('placed', 'pending') THEN 1 ELSE 0 END) as en_cours,
            SUM(CASE WHEN p.status = 'void' THEN 1 ELSE 0 END) as void,
            SUM(CASE WHEN p.status IN ('won', 'lost') THEN p.actual_profit ELSE 0 END) as profit_total,
            SUM(CASE WHEN p.status IN ('won', 'lost', 'void') THEN p.actual_stake ELSE 0 END) as mises_totales
        FROM pronostics p
        WHERE p.user_id = ?
        """,
        (current_user["id"],),
    ).fetchone()

    win_rate = None
    if stats["won"] is not None and stats["lost"] is not None:
        resolved = (stats["won"] or 0) + (stats["lost"] or 0)
        if resolved > 0:
            win_rate = round((stats["won"] or 0) / resolved, 4)

    roi = None
    mises = stats["mises_totales"] or 0
    profit = stats["profit_total"] or 0
    if mises > 0:
        roi = round(profit / mises, 4)

    items = []
    for p in rows:
        item = {
            "id": p["id"],
            "match": {
                "id": p["match_id"],
                "home_team": p["home_team"],
                "away_team": p["away_team"],
                "league": p["league_name"],
                "kickoff_timestamp": p["match_timestamp"],
                "score": (
                    f"{p['home_goals']}-{p['away_goals']}"
                    if p["home_goals"] is not None and p["away_goals"] is not None
                    else None
                ),
            },
            "market": p["market"],
            "market_label": MARKET_LABELS.get(p["market"], p["market"]),
            "status": p["status"],
            "confidence_score": p["confidence_score"],
            "model_probability": p["model_probability"],
            "reference_odds": p["reference_odds"],
            "recommended_stake": p["recommended_stake"],
            "actual_stake": p["actual_stake"],
            "actual_odds": p["actual_odds"],
            "actual_profit": p["actual_profit"],
            "expected_value": p["expected_value"],
            "recommended_at": p["recommended_at"],
            "placed_at": p["placed_at"],
            "resolved_at": p["resolved_at"],
        }
        items.append(item)

    return reponse_succes({
        "items": items,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 1,
        },
        "stats": {
            "total": stats["total"] or 0,
            "won": stats["won"] or 0,
            "lost": stats["lost"] or 0,
            "en_cours": stats["en_cours"] or 0,
            "void": stats["void"] or 0,
            "profit_total": round(profit, 2),
            "mises_totales": round(mises, 2),
            "win_rate": win_rate,
            "roi": roi,
        },
    })


class IgnoreRequest(BaseModel):
    reason: str = None


@router.post("/{pronostic_id}/ignore")
async def ignorer_pronostic(
    pronostic_id: int,
    req: IgnoreRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    pronostic = conn.execute(
        "SELECT status FROM pronostics WHERE id = ? AND user_id = ?",
        (pronostic_id, current_user["id"]),
    ).fetchone()

    if not pronostic:
        raise HTTPException(status_code=404, detail="Pronostic introuvable")

    if pronostic["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail="Seuls les pronostics en attente peuvent être ignorés",
        )

    conn.execute(
        """
        UPDATE pronostics SET
            status = 'ignored',
            ignored_at = datetime('now'),
            ignore_reason = ?
        WHERE id = ? AND user_id = ?
        """,
        (req.reason, pronostic_id, current_user["id"]),
    )
    conn.commit()

    return reponse_succes({"pronostic_id": pronostic_id, "status": "ignored"})
