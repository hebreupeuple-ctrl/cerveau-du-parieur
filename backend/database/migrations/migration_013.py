"""
Migration 013 — Correction des pronostics résolus sur scores pré-match.

FootyStats stocke homeGoalCount=0 avant le coup d'envoi. Si la résolution
s'est déclenchée avant que les vrais scores soient collectés, des pronostics
ont été marqués 'lost' à tort. On corrige en recalculant sur les scores
maintenant disponibles en base.
"""

import sqlite3

DESCRIPTION = "Correction pronostics mal résolus (scores pré-match 0/0)"


def _resultat(marche, hg, ag, tg, hg_ht, ag_ht) -> str:
    hg = hg or 0
    ag = ag or 0
    tg = tg if tg is not None else (hg + ag)
    if marche == "over25":
        return "won" if tg > 2 else "lost"
    elif marche == "over15":
        return "won" if tg > 1 else "lost"
    elif marche == "over35":
        return "won" if tg > 3 else "lost"
    elif marche == "btts":
        return "won" if (hg > 0 and ag > 0) else "lost"
    elif marche == "over15_ht":
        if hg_ht is None or ag_ht is None:
            return "void"
        return "won" if (hg_ht + ag_ht) > 1 else "lost"
    elif marche == "1x2_home":
        return "won" if hg > ag else "lost"
    elif marche == "1x2_draw":
        return "won" if hg == ag else "lost"
    elif marche == "1x2_away":
        return "won" if ag > hg else "lost"
    return "void"


def appliquer(conn: sqlite3.Connection) -> None:
    # Pronostics résolus où le match a depuis été mis à jour avec de vrais scores
    rows = conn.execute(
        """
        SELECT
            p.id, p.user_id, p.market, p.status as old_status,
            p.actual_stake, p.actual_odds, p.actual_profit,
            m.home_goals, m.away_goals, m.total_goals,
            m.home_goals_ht, m.away_goals_ht
        FROM pronostics p
        JOIN matches m ON p.match_id = m.id
        WHERE p.status IN ('won', 'lost')
        AND p.actual_stake IS NOT NULL
        AND p.actual_stake > 0
        AND m.home_goals IS NOT NULL
        AND m.away_goals IS NOT NULL
        AND datetime(m.updated_at) > datetime(p.resolved_at)
        """
    ).fetchall()

    corriges = 0
    for p in rows:
        new_result = _resultat(
            p["market"],
            p["home_goals"], p["away_goals"], p["total_goals"],
            p["home_goals_ht"], p["away_goals_ht"],
        )

        if new_result == p["old_status"]:
            continue

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
        corriges += 1

    if corriges:
        conn.commit()
