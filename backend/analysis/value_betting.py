"""
Moteur de Value Betting.
Compare les probabilites du modele avec les cotes bookmakers
pour identifier les paris avec valeur attendue positive.
"""

from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)

SEUIL_EV_MINIMUM = 0.05      # Relevé de 3 % à 5 % pour plus de sélectivité
SEUIL_EDGE_MINIMUM = 0.05


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
    Ajuste le seuil EV en fonction de la confiance du modèle.
    Plus la proba est haute, plus on tolère un EV légèrement plus faible
    (signal fort = on accepte une marge de valeur réduite).
    La réduction maximale est de 20 % du seuil de base.
    """
    if probabilite_modele >= 0.80:
        return seuil_base * 0.80
    if probabilite_modele >= 0.70:
        return seuil_base * 0.90
    return seuil_base


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


def detecter_mouvement_sharp(
    cotes_disponibles: dict,
    marche_cote_key: str,
) -> bool:
    """
    Détecte un mouvement de cote dit 'sharp' (action des parieurs professionnels).
    Un mouvement est sharp si la cote a baissé depuis l'ouverture (cote_ouverture > cote_actuelle)
    ET que le mouvement est supérieur à 5 % de la cote d'ouverture.
    Cela indique que de l'argent intelligent a parié dans ce sens.
    """
    movement_key = marche_cote_key.replace("odds_", "movement_")
    movement = cotes_disponibles.get(movement_key)
    if movement is None:
        return False
    # movement > 0 : cote a baissé depuis l'ouverture (signal sharp favorable)
    return float(movement) > 0.05


def analyser_match(
    probabilites_modele: dict,
    cotes_disponibles: dict,
    seuil_confiance: float = 0.60,
) -> list:
    """
    Analyse un match et retourne les opportunites de valeur.

    probabilites_modele : dict avec les probabilites calculees
    cotes_disponibles : dict avec les cotes bookmaker par marche
    """
    opportunites = []

    mapping_marches = {
        "over25": {
            "cote_key": "odds_over25",
            "label": "Plus de 2.5 buts",
        },
        "btts": {
            "cote_key": "odds_btts_yes",
            "label": "Les deux equipes marquent",
        },
        "over15": {
            "cote_key": "odds_over15",
            "label": "Plus de 1.5 buts",
        },
        "over15_ht": {
            "cote_key": "odds_over15_ht",
            "label": "Plus de 1.5 buts (mi-temps)",
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
    }

    prob_marche_modele = {
        "over25":    probabilites_modele.get("prob_over25"),
        "over15":    probabilites_modele.get("prob_over15"),
        "over15_ht": probabilites_modele.get("prob_over15_ht"),
        "btts":      probabilites_modele.get("prob_btts"),
        "1x2_home":  probabilites_modele.get("prob_home_win"),
        "1x2_draw":  probabilites_modele.get("prob_draw"),
        "1x2_away":  probabilites_modele.get("prob_away_win"),
    }

    # Pré-calcul des probabilités implicites corrigées pour les marchés binaires
    # (over/under, btts, HT) : on corrige la marge si les deux côtés sont disponibles
    corrections_binaires = {}
    paires_binaires = [
        ("odds_over15",    "odds_under15"),
        ("odds_over25",    "odds_under25"),
        ("odds_over35",    "odds_under35"),
        ("odds_over45",    "odds_under45"),
        ("odds_btts_yes",  "odds_btts_no"),
        ("odds_over15_ht", "odds_under15_ht"),
    ]
    for cle_yes, cle_no in paires_binaires:
        c_yes = cotes_disponibles.get(cle_yes)
        c_no = cotes_disponibles.get(cle_no)
        if c_yes and c_no and c_yes > 1.0 and c_no > 1.0:
            somme = 1.0 / c_yes + 1.0 / c_no
            if somme > 0:
                corrections_binaires[cle_yes] = (1.0 / c_yes) / somme
                corrections_binaires[cle_no] = (1.0 / c_no) / somme

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

        a_valeur = detecter_valeur(
            probabilite_modele=prob_modele,
            probabilite_bookmaker=prob_bk_corrigee,
            cote=cote_raw,
        )

        if a_valeur:
            is_sharp = detecter_mouvement_sharp(cotes_disponibles, cfg["cote_key"])
            opportunites.append({
                "marche": marche,
                "label": cfg["label"],
                "probabilite_modele": round(prob_modele, 4),
                "probabilite_bookmaker": round(prob_bk_corrigee, 4),
                "edge": round(edge, 4),
                "cote": cote_raw,
                "ev": ev,
                "confiance": round(prob_modele, 4),
                "sharp_signal": is_sharp,
            })

    opportunites.sort(key=lambda x: x["ev"], reverse=True)
    return opportunites
