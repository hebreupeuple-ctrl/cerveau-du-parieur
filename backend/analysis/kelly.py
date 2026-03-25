"""
Calcul du critere de Kelly pour la gestion de bankroll.
Kelly Adaptatif avec fractions variables selon le contexte.
"""

import math
from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)

MISE_MINIMUM = 5.0
MISE_MAXIMUM_PCT = 0.10
FRACTION_DEFAUT = 0.125


def calculer_kelly_simple(
    probabilite: float,
    cote: float,
) -> float:
    """
    Calcule la fraction Kelly pure.
    f = (b * p - q) / b
    Retourne 0 si EV negatif.
    """
    if cote <= 1.0 or probabilite <= 0 or probabilite >= 1:
        return 0.0

    b = cote - 1.0
    p = probabilite
    q = 1.0 - p

    kelly = (b * p - q) / b

    return max(0.0, round(kelly, 4))


def appliquer_fraction(
    kelly_brut: float,
    fraction: float,
) -> float:
    """
    Applique la fraction Kelly choisie.
    """
    return round(kelly_brut * fraction, 4)


def calculer_mise_finale(
    kelly_fraction: float,
    bankroll: float,
    mise_minimum: float = MISE_MINIMUM,
    mise_maximum_pct: float = MISE_MAXIMUM_PCT,
) -> float:
    """
    Calcule la mise finale en euros.

    Règles :
    - Si la mise naturelle (kelly_fraction * bankroll) est inférieure au
      minimum, on ne mise pas (forcer le minimum serait un overbet).
    - La mise est plafonnée à mise_maximum_pct de la bankroll.
    """
    if bankroll <= 0 or kelly_fraction <= 0:
        return 0.0

    mise_naturelle = kelly_fraction * bankroll

    # Ne pas forcer le minimum : si Kelly recommande moins, ne pas miser
    if mise_naturelle < mise_minimum:
        return 0.0

    mise_max = bankroll * mise_maximum_pct
    mise = min(mise_naturelle, mise_max)

    return round(mise, 2)


def calculer_fraction_adaptative(
    roi_historique: Optional[float],
    n_paris: int,
    bankroll_actuelle: float,
    bankroll_initiale: float,
    fraction_base: float = FRACTION_DEFAUT,
) -> float:
    """
    Calcule la fraction Kelly adaptative selon le contexte.

    Progression :
    - Debut (< 30 paris) : 1/8 (0.125)
    - Etabli (30-100 paris, ROI > 0) : 1/6 (0.167)
    - Mature (> 100 paris, ROI > 5%) : 1/4 (0.25)

    Protection :
    - Bankroll < 80% : fraction reduite de 50%
    - Bankroll < 60% : fraction minimale 1/8
    """
    fraction = fraction_base

    if n_paris >= 100 and roi_historique is not None:
        if roi_historique > 0.05:
            fraction = 0.25
        elif roi_historique > 0.0:
            fraction = 0.167
        else:
            fraction = 0.125
    elif n_paris >= 30 and roi_historique is not None:
        if roi_historique > 0.0:
            fraction = 0.167
        else:
            fraction = 0.125

    ratio_bankroll = bankroll_actuelle / max(bankroll_initiale, 1.0)

    # Appliqué séquentiellement : le palier < 60 % est toujours plus restrictif
    # que le palier < 80 %, quelle que soit la fraction de départ.
    if ratio_bankroll < 0.80:
        fraction = fraction * 0.5
    if ratio_bankroll < 0.60:
        # Hard-cap : même après le halving, ne dépasse pas 1/16
        fraction = min(fraction, 0.0625)

    return round(fraction, 4)


def calculer_mise_minimum_adaptative(bankroll: float) -> float:
    """
    Minimum de mise proportionnel à la bankroll.
    1 % de la bankroll, planché à 1 € et plafonné à 10 €.
    Évite le problème des petites bankrolls avec MISE_MINIMUM fixe.
    """
    return round(max(1.0, min(bankroll * 0.01, 10.0)), 2)


def calculer_kelly_complet(
    probabilite: float,
    cote: float,
    bankroll: float,
    bankroll_initiale: float,
    roi_historique: Optional[float] = None,
    n_paris: int = 0,
    fraction_override: Optional[float] = None,
) -> dict:
    """
    Calcul complet du Kelly avec toutes les protections.
    Retourne un dict avec tous les details.
    """
    kelly_brut = calculer_kelly_simple(probabilite, cote)

    if kelly_brut <= 0:
        return {
            "kelly_brut": 0.0,
            "fraction": 0.0,
            "kelly_avec_fraction": 0.0,
            "mise_recommandee": 0.0,
            "ev": 0.0,
            "a_valeur": False,
        }

    if fraction_override is not None:
        fraction = fraction_override
    else:
        fraction = calculer_fraction_adaptative(
            roi_historique=roi_historique,
            n_paris=n_paris,
            bankroll_actuelle=bankroll,
            bankroll_initiale=bankroll_initiale,
        )

    kelly_avec_fraction = appliquer_fraction(kelly_brut, fraction)

    mise = calculer_mise_finale(
        kelly_fraction=kelly_avec_fraction,
        bankroll=bankroll,
        mise_minimum=calculer_mise_minimum_adaptative(bankroll),
    )

    ev = (probabilite * cote) - 1.0

    from backend.core.config import settings
    return {
        "kelly_brut": kelly_brut,
        "fraction": fraction,
        "kelly_avec_fraction": kelly_avec_fraction,
        "mise_recommandee": mise,
        "ev": round(ev, 4),
        "a_valeur": ev >= settings.MIN_EV_THRESHOLD,
    }
