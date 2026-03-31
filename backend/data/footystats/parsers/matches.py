"""
Parser pour les données de matchs FootyStats.
Transforme les réponses brutes en dictionnaires propres.
"""

from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


def parser_match(data: dict) -> Optional[dict]:
    """
    Parse un match depuis la réponse FootyStats.
    Retourne None si les données sont invalides.
    """
    try:
        # Champs critiques — refus si manquants
        footystats_id = data.get("id")
        home_id = data.get("homeID")
        away_id = data.get("awayID")
        timestamp = data.get("date_unix")

        if not all([footystats_id, home_id, away_id, timestamp]):
            logger.warning_ctx(
                "Match ignoré : champs critiques manquants",
                context={"data": str(data)[:200]},
            )
            return None

        status_raw = data.get("status", "incomplete")
        status = _parser_status(status_raw)

        # Buts — None si match pas terminé
        home_goals = _safe_int(data.get("homeGoalCount"))
        away_goals = _safe_int(data.get("awayGoalCount"))
        total_goals = _safe_int(data.get("totalGoalCount"))

        # Résultat 1X2
        result_1x2 = None
        if home_goals is not None and away_goals is not None:
            if home_goals > away_goals:
                result_1x2 = "1"
            elif home_goals == away_goals:
                result_1x2 = "X"
            else:
                result_1x2 = "2"

        # Over/Under
        over15 = _safe_bool(data.get("o15"))
        over25 = _safe_bool(data.get("o25"))
        over45 = _safe_bool(data.get("o45"))

        if over25 is None and total_goals is not None:
            over25 = 1 if total_goals > 2 else 0

        if over15 is None and total_goals is not None:
            over15 = 1 if total_goals > 1 else 0

        # BTTS
        btts = _safe_bool(data.get("btts"))
        if btts is None and home_goals is not None and away_goals is not None:
            btts = 1 if (home_goals > 0 and away_goals > 0) else 0

        # Stats avancées
        home_xg = _safe_float(data.get("team_a_xg"))
        away_xg = _safe_float(data.get("team_b_xg"))

        return {
            "footystats_id": footystats_id,
            "home_team_footystats_id": home_id,
            "away_team_footystats_id": away_id,
            "match_timestamp": timestamp,
            "match_date": _timestamp_to_date(timestamp),
            "game_week": _safe_int(data.get("game_week")),
            "status": status,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "home_goals_ht": _safe_int(data.get("ht_goals_team_a")),
            "away_goals_ht": _safe_int(data.get("ht_goals_team_b")),
            "total_goals": total_goals,
            "result_1x2": result_1x2,
            "over15": over15,
            "over25": over25,
            "over45": over45,
            "btts": btts,
            "home_xg": home_xg,
            "away_xg": away_xg,
            "home_shots": _safe_int(data.get("team_a_shots")),
            "away_shots": _safe_int(data.get("team_b_shots")),
            "home_shots_on_target": _safe_int(
                data.get("team_a_shotsOnTarget")
            ),
            "away_shots_on_target": _safe_int(
                data.get("team_b_shotsOnTarget")
            ),
            "home_corners": _safe_int(data.get("team_a_corners")),
            "away_corners": _safe_int(data.get("team_b_corners")),
            "home_yellow_cards": _safe_int(
                data.get("team_a_yellow_cards")
            ),
            "away_yellow_cards": _safe_int(
                data.get("team_b_yellow_cards")
            ),
            "home_red_cards": _safe_int(data.get("team_a_red_cards")),
            "away_red_cards": _safe_int(data.get("team_b_red_cards")),
            "home_possession": _safe_float(
                data.get("team_a_possession")
            ),
            "away_possession": _safe_float(
                data.get("team_b_possession")
            ),
            "competition_type": "league",
        }

    except Exception as e:
        logger.error_ctx(
            "Erreur parsing match",
            context={
                "erreur": str(e),
                "data_id": data.get("id"),
            },
        )
        return None


def _parser_status(status_raw: str) -> str:
    """Normalise le statut d'un match."""
    mapping = {
        "complete": "complete",
        "incomplete": "upcoming",
        "suspended": "postponed",
        "canceled": "cancelled",
        "postponed": "postponed",
    }
    return mapping.get(status_raw.lower(), "upcoming")


def _safe_int(value) -> Optional[int]:
    """Convertit en int ou retourne None."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_float(value) -> Optional[float]:
    """Convertit en float ou retourne None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_bool(value) -> Optional[int]:
    """Convertit en 0/1 ou retourne None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return 1 if value else 0
    return None


def _timestamp_to_date(timestamp: int) -> str:
    """Convertit un timestamp Unix en date ISO."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(
        timestamp, tz=timezone.utc
    ).strftime("%Y-%m-%d")
