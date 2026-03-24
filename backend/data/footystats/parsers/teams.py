"""
Parser pour les données d'équipes FootyStats.
"""

from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


def parser_equipe(data: dict) -> Optional[dict]:
    """
    Parse une équipe depuis la réponse FootyStats.
    """
    try:
        team_id = data.get("id")
        name = data.get("name") or data.get("cleanName")

        if not team_id or not name:
            return None

        return {
            "footystats_id": team_id,
            "name": name,
            "country": data.get("country", "Unknown"),
            "founded_year": None,
        }

    except Exception as e:
        logger.error_ctx(
            "Erreur parsing équipe",
            context={"erreur": str(e)},
        )
        return None
