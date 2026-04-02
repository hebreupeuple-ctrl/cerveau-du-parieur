"""
Moteur de Value Betting.
Compare les probabilites du modele avec les cotes bookmakers
pour identifier les paris avec valeur attendue positive.
"""

from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)

SEUIL_EV_MINIMUM = 0.03
SEUIL_EDGE_MINIMUM = 0.03


def corriger_marge_bookmaker(cotes: dict) -> dict:
    """
    Retire la marge du bookmaker des cotes brutes.
    Retourne les probabilites reelles.
    """
    probas_brutes = {}
    for marche, cote in cotes.items():
        if cote and cote > 1.0:
            probas_brutes[marche] = 1.0 / cote

    somme = sum(probas_brutes.values())
    if somme <= 0:
        return {}

    marge = somme - 1.0
    probas_corrigees = {
        k: v / somme for k, v in probas_brutes.items()
    }
    probas_corrigees["marge"] = round(marge, 4)

    return probas_corrigees


def calculer_ev(
    probabilite_modele: float,
    cote: float,
) -> float:
    """
    Calcule la valeur attendue d'un pari.
    EV = (probabilite * cote) - 1
    """
    if not cote or cote <= 1.0:
        return -1.0
    return round((probabilite_modele * cote) - 1.0, 4)


def seuil_ev_adaptatif(
    probabilite_modele: float,
    seuil_base: float = SEUIL_EV_MINIMUM,
) -> float:
    """
    Seuil EV plus strict quand la confiance est faible — fonction continue.
    Élimine les sauts brusques (anciens paliers durs à 0.65 et 0.70).

    prob >= 0.70 → seuil standard
    prob  = 0.50 → seuil * 1.50 (+50 % de marge de sécurité)
    Entre les deux : interpolation linéaire.
    """
    if probabilite_modele >= 0.70:
        return seuil_base
    penalite = min(1.0, (0.70 - probabilite_modele) / 0.20)
    return round(seuil_base * (1.0 + 0.5 * penalite), 4)


def detecter_valeur(
    probabilite_modele: float,
    probabilite_bookmaker: float,
    cote: float,
    seuil_ev: float = SEUIL_EV_MINIMUM,
    seuil_edge: float = SEUIL_EDGE_MINIMUM,
) -> bool:
    """
    Detecte si un pari a une valeur positive suffisante.
    Le seuil EV est adaptatif selon la confiance du modèle.
    """
    ev = calculer_ev(probabilite_modele, cote)
    edge = probabilite_modele - probabilite_bookmaker
    seuil_ev_reel = seuil_ev_adaptatif(probabilite_modele, seuil_ev)

    return ev >= seuil_ev_reel and edge >= seuil_edge



def analyser_match(
    probabilites_modele: dict,
    cotes_disponibles: dict,
    seuil_confiance: float = 0.60,
    cotes_reelles: bool = True,
) -> list:
    """
    Analyse un match et retourne les opportunites de valeur.

    probabilites_modele : dict avec les probabilites calculees
    cotes_disponibles : dict avec les cotes bookmaker par marche
    """
    opportunites = []

    # Dériver les cotes Double Chance depuis les cotes 1X2 bookmaker si disponibles
    c_home = cotes_disponibles.get("odds_home")
    c_draw_raw = cotes_disponibles.get("odds_draw")
    c_away = cotes_disponibles.get("odds_away")
    if c_home and c_draw_raw and c_away and all(c > 1.0 for c in [c_home, c_draw_raw, c_away]):
        somme_1x2 = 1.0 / c_home + 1.0 / c_draw_raw + 1.0 / c_away
        if somme_1x2 > 0:
            p_bk_home = (1.0 / c_home) / somme_1x2
            p_bk_draw = (1.0 / c_draw_raw) / somme_1x2
            p_bk_away = (1.0 / c_away) / somme_1x2
            if "odds_dc_1x" not in cotes_disponibles:
                p_dc_1x = p_bk_home + p_bk_draw
                if p_dc_1x > 0:
                    cotes_disponibles = dict(cotes_disponibles)
                    cotes_disponibles["odds_dc_1x"] = round(1.0 / p_dc_1x, 2)
            if "odds_dc_x2" not in cotes_disponibles:
                p_dc_x2 = p_bk_draw + p_bk_away
                if p_dc_x2 > 0:
                    cotes_disponibles = dict(cotes_disponibles)
                    cotes_disponibles["odds_dc_x2"] = round(1.0 / p_dc_x2, 2)

    # Dériver la cote GG & Over 2.5 depuis odds_btts_yes et odds_over25 si disponibles
    c_btts = cotes_disponibles.get("odds_btts_yes")
    c_o25 = cotes_disponibles.get("odds_over25")
    if c_btts and c_o25 and c_btts > 1.0 and c_o25 > 1.0:
        if "odds_gg_over25" not in cotes_disponibles:
            # P(GG & Over 2.5) ≈ P(GG) × P(Over 2.5) — approximation par indépendance
            p_combined = (1.0 / c_btts) * (1.0 / c_o25)
            if p_combined > 0.01:
                cotes_disponibles = dict(cotes_disponibles)
                cotes_disponibles["odds_gg_over25"] = round(1.0 / p_combined, 2)

    # Cotes fixes du marché "quelle mi-temps a le plus de buts"
    # Ces cotes ne varient jamais selon le bookmaker — on les injecte toujours.
    cotes_disponibles = dict(cotes_disponibles)
    cotes_disponibles.setdefault("odds_more_goals_1st",   3.10)
    cotes_disponibles.setdefault("odds_more_goals_equal", 3.00)
    cotes_disponibles.setdefault("odds_more_goals_2nd",   2.10)

    mapping_marches = {
        "over15": {
            "cote_key": "odds_over15",
            "label": "Plus de 1.5 buts",
        },
        "over25": {
            "cote_key": "odds_over25",
            "label": "Plus de 2.5 buts",
        },
        "over45": {
            "cote_key": "odds_over45",
            "label": "Plus de 4.5 buts",
        },
        "btts": {
            "cote_key": "odds_btts_yes",
            "label": "Les deux equipes marquent",
        },
        "1x2_home": {
            "cote_key": "odds_home",
            "label": "Victoire domicile",
        },
        "1x2_draw": {
            "cote_key": "odds_draw",
            "label": "Match nul",
        },
        "1x2_away": {
            "cote_key": "odds_away",
            "label": "Victoire exterieur",
        },
        "dc_1x": {
            "cote_key": "odds_dc_1x",
            "label": "Double chance 1X (domicile ou nul)",
        },
        "dc_x2": {
            "cote_key": "odds_dc_x2",
            "label": "Double chance X2 (nul ou extérieur)",
        },
        "gg_over25": {
            "cote_key": "odds_gg_over25",
            "label": "Les deux marquent & plus de 2.5 buts",
        },
        "1x2_ht_home": {
            "cote_key": "odds_ht_home",
            "label": "Victoire domicile à la mi-temps",
        },
        "1x2_ht_draw": {
            "cote_key": "odds_ht_draw",
            "label": "Nul à la mi-temps",
        },
        "1x2_ht_away": {
            "cote_key": "odds_ht_away",
            "label": "Victoire extérieur à la mi-temps",
        },
        "over15_ht": {
            "cote_key": "odds_over15_ht",
            "label": "Mi-temps : plus de 1.5 buts",
        },
        "more_goals_1st": {
            "cote_key": "odds_more_goals_1st",
            "label": "Plus de buts en 1ère mi-temps",
        },
        "more_goals_equal": {
            "cote_key": "odds_more_goals_equal",
            "label": "Autant de buts dans chaque mi-temps",
        },
        "more_goals_2nd": {
            "cote_key": "odds_more_goals_2nd",
            "label": "Plus de buts en 2ème mi-temps",
        },
    }

    # Dériver les cotes 1X2 HT depuis les cotes 1X2 FT si les cotes HT ne sont pas en DB
    # (approximation : HT odds ≈ 1/P_ht avec marge 12%)
    for marche_ht, prob_key, cote_key in [
        ("1x2_ht_home", "prob_ht_home_win", "odds_ht_home"),
        ("1x2_ht_draw", "prob_ht_draw",     "odds_ht_draw"),
        ("1x2_ht_away", "prob_ht_away_win", "odds_ht_away"),
        ("over15_ht",   "prob_over15_ht",   "odds_over15_ht"),
    ]:
        if cote_key not in cotes_disponibles:
            p = probabilites_modele.get(prob_key)
            if p and p > 0.05:
                cotes_disponibles = dict(cotes_disponibles)
                cotes_disponibles[cote_key] = round(1.12 / p, 2)

    prob_marche_modele = {
        "over15":      probabilites_modele.get("prob_over15"),
        "over25":      probabilites_modele.get("prob_over25"),
        "over45":      probabilites_modele.get("prob_over45"),
        "btts":        probabilites_modele.get("prob_btts"),
        "1x2_home":    probabilites_modele.get("prob_home_win"),
        "1x2_draw":    probabilites_modele.get("prob_draw"),
        "1x2_away":    probabilites_modele.get("prob_away_win"),
        "dc_1x":       probabilites_modele.get("prob_dc_1x"),
        "dc_x2":       probabilites_modele.get("prob_dc_x2"),
        "gg_over25":   probabilites_modele.get("prob_gg_over25"),
        "1x2_ht_home":    probabilites_modele.get("prob_ht_home_win"),
        "1x2_ht_draw":    probabilites_modele.get("prob_ht_draw"),
        "1x2_ht_away":    probabilites_modele.get("prob_ht_away_win"),
        "over15_ht":      probabilites_modele.get("prob_over15_ht"),
        "more_goals_1st":   probabilites_modele.get("prob_more_goals_1st"),
        "more_goals_equal": probabilites_modele.get("prob_more_goals_equal"),
        "more_goals_2nd":   probabilites_modele.get("prob_more_goals_2nd"),
    }

    # Pré-calcul des probabilités implicites corrigées pour les marchés binaires
    # (over/under, btts, HT) : on corrige la marge si les deux côtés sont disponibles
    corrections_binaires = {}
    paires_binaires = [
        ("odds_over15",   "odds_under15"),
        ("odds_over25",   "odds_under25"),
        ("odds_over45",   "odds_under45"),
        ("odds_home",     "odds_away"),
    ]
    for cle_yes, cle_no in paires_binaires:
        c_yes = cotes_disponibles.get(cle_yes)
        c_no = cotes_disponibles.get(cle_no)
        if c_yes and c_no and c_yes > 1.0 and c_no > 1.0:
            somme = 1.0 / c_yes + 1.0 / c_no
            if somme > 0:
                corrections_binaires[cle_yes] = (1.0 / c_yes) / somme
                corrections_binaires[cle_no] = (1.0 / c_no) / somme

    # Correction marge marché "quelle mi-temps a le plus de buts" (3 voies)
    c_mg1 = cotes_disponibles.get("odds_more_goals_1st")
    c_mge = cotes_disponibles.get("odds_more_goals_equal")
    c_mg2 = cotes_disponibles.get("odds_more_goals_2nd")
    if c_mg1 and c_mge and c_mg2 and all(c > 1.0 for c in [c_mg1, c_mge, c_mg2]):
        somme_mg = 1.0 / c_mg1 + 1.0 / c_mge + 1.0 / c_mg2
        if somme_mg > 0:
            corrections_binaires["odds_more_goals_1st"]   = (1.0 / c_mg1) / somme_mg
            corrections_binaires["odds_more_goals_equal"] = (1.0 / c_mge) / somme_mg
            corrections_binaires["odds_more_goals_2nd"]   = (1.0 / c_mg2) / somme_mg

    # Correction 1x2
    c_home = cotes_disponibles.get("odds_home")
    c_draw = cotes_disponibles.get("odds_draw")
    c_away = cotes_disponibles.get("odds_away")
    if c_home and c_draw and c_away and all(c > 1.0 for c in [c_home, c_draw, c_away]):
        somme_1x2 = 1.0 / c_home + 1.0 / c_draw + 1.0 / c_away
        if somme_1x2 > 0:
            corrections_binaires["odds_home"] = (1.0 / c_home) / somme_1x2
            corrections_binaires["odds_draw"] = (1.0 / c_draw) / somme_1x2
            corrections_binaires["odds_away"] = (1.0 / c_away) / somme_1x2

    for marche, cfg in mapping_marches.items():
        prob_modele = prob_marche_modele.get(marche)
        cote_raw = cotes_disponibles.get(cfg["cote_key"])

        if not prob_modele or not cote_raw:
            continue

        if prob_modele < seuil_confiance:
            continue

        if cote_raw <= 1.0:
            continue

        # Probabilité bookmaker corrigée de la marge si disponible, sinon brute
        prob_bk_corrigee = corrections_binaires.get(
            cfg["cote_key"], 1.0 / cote_raw
        )

        ev = calculer_ev(prob_modele, cote_raw)
        edge = prob_modele - prob_bk_corrigee

        # Sans cotes bookmaker réelles, l'edge est circulaire (mesuré contre
        # nos propres cotes générées). On compense en doublant le seuil EV
        # et en conservant un seuil edge minimal pour éviter les paris
        # où le modèle est lui-même en dessous de son propre implied prob.
        if cotes_reelles:
            seuil_ev_effectif = SEUIL_EV_MINIMUM
            seuil_edge_effectif = SEUIL_EDGE_MINIMUM
        else:
            seuil_ev_effectif = SEUIL_EV_MINIMUM * 2.0
            seuil_edge_effectif = 0.0
        a_valeur = detecter_valeur(
            probabilite_modele=prob_modele,
            probabilite_bookmaker=prob_bk_corrigee,
            cote=cote_raw,
            seuil_ev=seuil_ev_effectif,
            seuil_edge=seuil_edge_effectif,
        )

        if a_valeur:
            opportunites.append({
                "marche": marche,
                "label": cfg["label"],
                "probabilite_modele": round(prob_modele, 4),
                "probabilite_bookmaker": round(prob_bk_corrigee, 4),
                "edge": round(edge, 4),
                "cote": cote_raw,
                "ev": ev,
                "confiance": round(prob_modele, 4),
            })

    opportunites.sort(key=lambda x: x["ev"], reverse=True)
    return opportunites
