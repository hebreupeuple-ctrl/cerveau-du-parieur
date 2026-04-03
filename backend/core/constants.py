"""
Constantes globales du système.
"""

# Groupes de ligues
MAJOR_EUROPEAN_LEAGUES = [
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Champions League",
]

# IDs FootyStats des grandes ligues
MAJOR_LEAGUE_IDS = {
    "Premier League": 1625,
    "La Liga": 1869,
    "Serie A": 1854,
    "Bundesliga": 1867,
    "Ligue 1": 1871,
    "Champions League": 1005,
}

# Fuseaux horaires par ligue
LEAGUE_TIMEZONES = {
    "Premier League": "Europe/London",
    "La Liga": "Europe/Madrid",
    "Serie A": "Europe/Rome",
    "Bundesliga": "Europe/Berlin",
    "Ligue 1": "Europe/Paris",
    "Champions League": "Europe/London",
    "MLS": "America/New_York",
    "Liga MX": "America/Mexico_City",
    "Brasileirao": "America/Sao_Paulo",
    "J1 League": "Asia/Tokyo",
    "K League": "Asia/Seoul",
    "default": "UTC",
}

# Marchés disponibles
MARKETS = [
    "over15",
    "under15",
    "over25",
    "under25",
    "over35",
    "over45",
    "btts",
    "btts_no",
    "dc_12",
    "1x2_home",
    "1x2_draw",
    "1x2_away",
    "gg_over25",
    "over05_ht",
    "over15_ht",
    "over25_ht",
    "1x2_ht_home",
    "1x2_ht_draw",
    "1x2_ht_away",
    "more_goals_1st",
    "more_goals_equal",
    "more_goals_2nd",
]

# Labels lisibles des marchés
MARKET_LABELS = {
    "over15":     "Plus de 1.5 buts",
    "under15":    "Moins de 1.5 buts",
    "over25":     "Plus de 2.5 buts",
    "under25":    "Moins de 2.5 buts",
    "over35":     "Plus de 3.5 buts",
    "over45":     "Plus de 4.5 buts",
    "btts":       "Les deux équipes marquent",
    "btts_no":    "Les deux équipes ne marquent pas",
    "dc_12":      "Double chance 1-2 (pas de nul)",
    "1x2_home":   "Victoire domicile",
    "1x2_draw":   "Match nul",
    "1x2_away":   "Victoire extérieur",
    "gg_over25":  "Les deux marquent et plus de 2.5",
    "over05_ht":  "Mi-temps : plus de 0.5 buts",
    "over15_ht":  "Mi-temps : plus de 1.5 buts",
    "over25_ht":  "Mi-temps : plus de 2.5 buts",
    "1x2_ht_home": "Mi-temps : victoire domicile",
    "1x2_ht_draw": "Mi-temps : match nul",
    "1x2_ht_away":    "Mi-temps : victoire extérieur",
    "more_goals_1st":   "Plus de buts en 1ère mi-temps",
    "more_goals_equal": "Autant de buts dans chaque mi-temps",
    "more_goals_2nd":   "Plus de buts en 2ème mi-temps",
}

# Statuts des pronostics
PRONOSTIC_STATUS = {
    "PENDING": "pending",
    "PLACED": "placed",
    "IGNORED": "ignored",
    "WON": "won",
    "LOST": "lost",
    "VOID": "void",
}

# Statuts des matchs
MATCH_STATUS = {
    "UPCOMING": "upcoming",
    "LIVE": "live",
    "COMPLETE": "complete",
    "CANCELLED": "cancelled",
    "POSTPONED": "postponed",
}

# Modes du système
SYSTEM_MODES = {
    "ACTIVE": "active",
    "REDUCED": "reduced",
    "MAINTENANCE": "maintenance",
}

# Fractions Kelly
KELLY_FRACTIONS = {
    "very_conservative": 0.125,
    "conservative": 0.167,
    "moderate": 0.25,
    "aggressive": 0.333,
}

# Profils tactiques
TACTICAL_PROFILES = [
    "high_press",
    "counter_attack",
    "low_block",
    "possession",
    "direct_play",
    "balanced",
]

# Seuils de biais
BIAS_WARNING_THRESHOLD = 15.0
BIAS_CRITICAL_THRESHOLD = 25.0

# TTL des notifications en secondes
NOTIFICATION_TTL = {
    "pronostic": 14400,
    "resultat": 43200,
    "financiere": 86400,
    "systeme": 86400,
    "rapport": 259200,
}

# Nombre maximum de buts dans la matrice
MAX_GOALS_MATRIX = 8

# Fenêtres de forme
FORM_WINDOWS = [3, 5, 10, 20]

# Paramètre de décroissance temporelle Dixon-Coles
XI = 0.0065
