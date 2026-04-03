"""
Logique centralisée de calcul des résultats de marchés sportifs.
Source unique de vérité utilisée par pronostics, analyse et automation.
"""


def calculer_resultat_marche(
    marche: str,
    home_goals: int,
    away_goals: int,
    home_goals_ht: int = None,
    away_goals_ht: int = None,
) -> bool | None:
    """
    Retourne True si la prédiction était correcte, False sinon,
    None si les données sont insuffisantes (match non terminé ou mi-temps inconnue).
    """
    if home_goals is None or away_goals is None:
        return None

    total = home_goals + away_goals

    if marche == "over15":    return total > 1
    if marche == "under15":   return total < 2
    if marche == "over25":    return total > 2
    if marche == "under25":   return total < 3
    if marche == "over35":    return total > 3
    if marche == "over45":    return total > 4
    if marche == "btts":      return home_goals > 0 and away_goals > 0
    if marche == "btts_no":   return home_goals == 0 or away_goals == 0
    if marche == "ng":        return home_goals == 0 and away_goals == 0
    if marche == "dc_1x":     return home_goals >= away_goals
    if marche == "dc_x2":     return away_goals >= home_goals
    if marche == "dc_12":     return home_goals != away_goals
    if marche == "gg_over25": return home_goals > 0 and away_goals > 0 and total > 2
    if marche == "1x2_home":  return home_goals > away_goals
    if marche == "1x2_draw":  return home_goals == away_goals
    if marche == "1x2_away":  return away_goals > home_goals

    # Marchés mi-temps
    if home_goals_ht is None or away_goals_ht is None:
        return None
    if marche == "1x2_ht_home": return home_goals_ht > away_goals_ht
    if marche == "1x2_ht_draw": return home_goals_ht == away_goals_ht
    if marche == "1x2_ht_away": return away_goals_ht > home_goals_ht
    if marche == "over05_ht":   return (home_goals_ht + away_goals_ht) > 0
    if marche == "over15_ht":   return (home_goals_ht + away_goals_ht) > 1
    if marche == "over25_ht":   return (home_goals_ht + away_goals_ht) > 2

    ht = home_goals_ht + away_goals_ht
    st = (home_goals + away_goals) - ht
    if marche == "more_goals_1st":   return ht > st
    if marche == "more_goals_equal": return ht == st
    if marche == "more_goals_2nd":   return st > ht

    return None


def calculer_resultat_marche_str(
    marche: str = None,
    home_goals: int = None,
    away_goals: int = None,
    home_goals_ht: int = None,
    away_goals_ht: int = None,
    market: str = None,
) -> str:
    """
    Variante retournant 'won', 'lost' ou 'void' (utilisée par le scheduler).
    Accepte 'marche' ou 'market' comme nom de paramètre.
    """
    m = marche or market
    result = calculer_resultat_marche(m, home_goals, away_goals, home_goals_ht, away_goals_ht)
    if result is None:
        return "void"
    return "won" if result else "lost"
