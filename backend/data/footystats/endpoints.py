"""
Définition de tous les endpoints FootyStats utilisés.
"""


class FootyStatsEndpoints:
    """
    Constantes pour tous les endpoints de l'API.
    """

    # Ligues et saisons
    LEAGUE_LIST = "league-list"
    LEAGUE_SEASON = "league-season"

    # Matchs
    LEAGUE_MATCHES = "league-matches"
    MATCH_DETAILS = "match"
    TODAYS_MATCHES = "todays-matches"

    # Statistiques équipes
    TEAM = "team"
    LEAGUE_TEAMS = "league-teams"

    # Statistiques avancées
    BTTS_STATS = "stats-data-btts"
    OVER25_STATS = "stats-data-over25"

    # Paramètres communs
    @staticmethod
    def params_matchs_saison(
        season_id: int,
        page: int = 1,
        max_per_page: int = 500,
        max_time: int = None,
    ) -> dict:
        params = {
            "season_id": season_id,
            "page": page,
            "max_per_page": max_per_page,
        }
        if max_time:
            params["max_time"] = max_time
        return params

    @staticmethod
    def params_matchs_aujourdhui() -> dict:
        return {"timezone": "UTC"}
