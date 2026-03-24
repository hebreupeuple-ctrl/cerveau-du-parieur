"""
Parser pour les données de ligues FootyStats.
"""

from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


def parser_ligue(data: dict) -> Optional[dict]:
    """
    Parse une ligue depuis la réponse FootyStats.
    """
    try:
        league_id = data.get("id")
        name = data.get("name")

        if not league_id or not name:
            return None

        return {
            "footystats_id": league_id,
            "name": name,
            "country": data.get("country", "Unknown"),
            "season_id": data.get("season", {}).get("id"),
            "season_name": data.get("season", {}).get("name", ""),
        }

    except Exception as e:
        logger.error_ctx(
            "Erreur parsing ligue",
            context={"erreur": str(e)},
        )
        return None


def parser_saison(data: dict, league_id: int) -> Optional[dict]:
    """
    Parse une saison depuis la réponse FootyStats.
    """
    try:
        season_id = data.get("id")
        if not season_id:
            return None

        return {
            "footystats_id": season_id,
            "league_id": league_id,
            "name": data.get("name", ""),
            "year": _extraire_annee(data.get("name", "")),
            "start_date": data.get("starting_year", "2024-01-01"),
            "end_date": data.get("ending_year", "2025-12-31"),
            "status": "active",
        }

    except Exception as e:
        logger.error_ctx(
            "Erreur parsing saison",
            context={"erreur": str(e)},
        )
        return None


def _extraire_annee(nom_saison: str) -> int:
    """
    Extrait l'année depuis un nom de saison.
    Exemple : '2024/2025' -> 2024
    """
    try:
        parts = nom_saison.split("/")
        return int(parts[0].strip())
    except (ValueError, IndexError):
        from datetime import datetime
        return datetime.now().year
