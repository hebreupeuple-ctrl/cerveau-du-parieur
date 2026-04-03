"""
Features probabilités implicites bookmaker.

Les bookmakers emploient des centaines d'analystes et disposent de bien plus
de données que nous. Leurs probabilités implicites (1/cote, corrigée de la marge)
sont le signal le plus précis disponible sur un match.

Injecter ces probabilités directement dans le modèle ML lui permet d'apprendre
QUAND il diverge du consensus bookmaker — c'est exactement là que se trouve la valeur.

Features calculées :
- bk_prob_home / bk_prob_draw / bk_prob_away  (marché 1X2 — référence principale)
- bk_prob_over15 / bk_prob_over25             (marchés over — les plus liquides)
- bk_prob_btts                                (marché BTTS)
- bk_margin                                   (marge bookmaker : < 5% = marché compétitif)
- bk_has_odds                                 (flag : 1 si cotes disponibles, 0 sinon)
"""

import sqlite3
from typing import Optional


def calculer_features_odds_implied(
    conn: sqlite3.Connection,
    match_id: int,
) -> dict:
    """
    Retourne les probabilités implicites bookmaker pour un match.
    Utilise les cotes les plus récentes collectées (toujours avant le match).

    Les probabilités corrigées de la marge (prob_*_corrected) sont utilisées
    quand elles existent en base. Sinon calculées depuis les cotes brutes.
    """
    row = conn.execute(
        """
        SELECT
            odds_home, odds_draw, odds_away,
            odds_over15, odds_under15,
            odds_over25, odds_under25,
            odds_btts_yes, odds_btts_no,
            prob_home_corrected, prob_draw_corrected, prob_away_corrected,
            prob_over25_corrected, prob_btts_corrected
        FROM odds
        WHERE match_id = ?
        ORDER BY collected_timestamp DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()

    if not row:
        return {
            "bk_prob_home":   None,
            "bk_prob_draw":   None,
            "bk_prob_away":   None,
            "bk_prob_over15": None,
            "bk_prob_over25": None,
            "bk_prob_btts":   None,
            "bk_margin":      None,
            "bk_has_odds":    0.0,
        }

    def safe(v) -> Optional[float]:
        return float(v) if v is not None else None

    # ── 1X2 : utilise prob corrigée si disponible ─────────────────────────
    prob_home = safe(row["prob_home_corrected"])
    prob_draw = safe(row["prob_draw_corrected"])
    prob_away = safe(row["prob_away_corrected"])

    # Fallback : calculer depuis cotes brutes
    if prob_home is None or prob_draw is None or prob_away is None:
        h = safe(row["odds_home"])
        d = safe(row["odds_draw"])
        a = safe(row["odds_away"])
        if h and d and a and h > 1.0 and d > 1.0 and a > 1.0:
            total = 1/h + 1/d + 1/a
            prob_home = round((1/h) / total, 4)
            prob_draw = round((1/d) / total, 4)
            prob_away = round((1/a) / total, 4)
        else:
            prob_home = prob_draw = prob_away = None

    # ── Over 2.5 : utilise prob corrigée si disponible ────────────────────
    prob_over25 = safe(row["prob_over25_corrected"])
    if prob_over25 is None:
        o25 = safe(row["odds_over25"])
        u25 = safe(row["odds_under25"])
        if o25 and u25 and o25 > 1.0 and u25 > 1.0:
            total_25 = 1/o25 + 1/u25
            prob_over25 = round((1/o25) / total_25, 4)

    # ── Over 1.5 : pas de colonne corrigée → calculer depuis brutes ───────
    prob_over15 = None
    o15 = safe(row["odds_over15"])
    u15 = safe(row["odds_under15"])
    if o15 and u15 and o15 > 1.0 and u15 > 1.0:
        total_15 = 1/o15 + 1/u15
        prob_over15 = round((1/o15) / total_15, 4)

    # ── BTTS : utilise prob corrigée si disponible ────────────────────────
    prob_btts = safe(row["prob_btts_corrected"])
    if prob_btts is None:
        b_yes = safe(row["odds_btts_yes"])
        b_no  = safe(row["odds_btts_no"])
        if b_yes and b_no and b_yes > 1.0 and b_no > 1.0:
            total_btts = 1/b_yes + 1/b_no
            prob_btts = round((1/b_yes) / total_btts, 4)

    # ── Marge bookmaker (overround - 1) ───────────────────────────────────
    # Marge faible (< 0.04) = marché compétitif = probabilités plus fiables.
    # Marge forte (> 0.08) = marché moins liquide = signal moins fiable.
    bk_margin = None
    h_raw = safe(row["odds_home"])
    d_raw = safe(row["odds_draw"])
    a_raw = safe(row["odds_away"])
    if h_raw and d_raw and a_raw and h_raw > 1.0 and d_raw > 1.0 and a_raw > 1.0:
        bk_margin = round((1/h_raw + 1/d_raw + 1/a_raw) - 1.0, 4)

    has_odds = 1.0 if prob_home is not None else 0.0

    return {
        "bk_prob_home":   round(prob_home, 4) if prob_home is not None else None,
        "bk_prob_draw":   round(prob_draw, 4) if prob_draw is not None else None,
        "bk_prob_away":   round(prob_away, 4) if prob_away is not None else None,
        "bk_prob_over15": prob_over15,
        "bk_prob_over25": prob_over25,
        "bk_prob_btts":   prob_btts,
        "bk_margin":      bk_margin,
        "bk_has_odds":    has_odds,
    }
