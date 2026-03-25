"""
Collecteur de cotes depuis FootyStats.
"""

import sqlite3
import time
import asyncio
from backend.core.logging import get_logger
from backend.database.connection import obtenir_connexion
from backend.data.footystats.client import FootyStatsClient

logger = get_logger(__name__)


class OddsCollector:

    def __init__(self, conn: sqlite3.Connection = None):
        self.conn = conn or obtenir_connexion()
        self.client = FootyStatsClient()

    async def collecter_cotes_match(self, match_id: int, footystats_match_id: int) -> bool:
        try:
            response = await self.client.get(
                "match",
                params={"match_id": footystats_match_id},
            )
            data = response.get("data", {})
            if isinstance(data, list):
                data = data[0] if data else {}
            if not data:
                return False
            cotes = self._extraire_cotes(data)
            if not cotes:
                return False
            self._sauvegarder_cotes(match_id, cotes)
            return True
        except Exception as e:
            logger.error_ctx(
                "Erreur collecte cotes",
                context={"match_id": match_id, "erreur": str(e)},
            )
            return False

    def _extraire_cotes(self, data: dict) -> dict:
        def safe_float(val):
            try:
                f = float(val)
                return f if f > 1.0 else None
            except (TypeError, ValueError):
                return None

        def get_first(*keys):
            """Retourne la première valeur non-None parmi les clés données."""
            for k in keys:
                v = safe_float(data.get(k))
                if v is not None:
                    return v
            return None

        cotes = {
            # FootyStats utilise odds_ft_1/x/2 (nouveau) ou odds_1/x/2 (ancien)
            "odds_home":      get_first("odds_ft_1", "odds_1"),
            "odds_draw":      get_first("odds_ft_x", "odds_x"),
            "odds_away":      get_first("odds_ft_2", "odds_2"),
            "odds_over15":    get_first("odds_ft_over15", "odds_over15"),
            "odds_under15":   get_first("odds_ft_under15", "odds_under15"),
            "odds_over25":    get_first("odds_ft_over25", "odds_over25"),
            "odds_under25":   get_first("odds_ft_under25", "odds_under25"),
            "odds_over35":    get_first("odds_ft_over35", "odds_over35"),
            "odds_under35":   get_first("odds_ft_under35", "odds_under35"),
            "odds_over45":    get_first("odds_ft_over45", "odds_over45"),
            "odds_under45":   get_first("odds_ft_under45", "odds_under45"),
            "odds_btts_yes":  safe_float(data.get("odds_btts_yes")),
            "odds_btts_no":   safe_float(data.get("odds_btts_no")),
            # Mi-temps : odds_1st_half_over15 (nouveau) ou odds_over15_ht (ancien)
            "odds_over15_ht": get_first("odds_1st_half_over15", "odds_over15_ht"),
            "odds_under15_ht": get_first("odds_1st_half_under15", "odds_under15_ht"),
        }
        return {k: v for k, v in cotes.items() if v is not None}

    def _sauvegarder_cotes(self, match_id: int, cotes: dict) -> None:
        maintenant = int(time.time())

        row = self.conn.execute(
            "SELECT match_timestamp FROM matches WHERE id = ?",
            (match_id,),
        ).fetchone()

        heures_avant = None
        if row:
            diff = row["match_timestamp"] - maintenant
            heures_avant = round(diff / 3600, 1)

        prob_over25 = round(1 / cotes["odds_over25"], 4) if cotes.get("odds_over25") else None
        prob_btts = round(1 / cotes["odds_btts_yes"], 4) if cotes.get("odds_btts_yes") else None

        # Correction de marge pour over45
        prob_over45 = None
        o45 = cotes.get("odds_over45")
        u45 = cotes.get("odds_under45")
        if o45 and u45 and o45 > 1.0 and u45 > 1.0:
            somme45 = 1.0 / o45 + 1.0 / u45
            if somme45 > 0:
                prob_over45 = round((1.0 / o45) / somme45, 4)

        # Correction de marge pour over15_ht
        prob_over15_ht = None
        o15ht = cotes.get("odds_over15_ht")
        u15ht = cotes.get("odds_under15_ht")
        if o15ht and u15ht and o15ht > 1.0 and u15ht > 1.0:
            somme15ht = 1.0 / o15ht + 1.0 / u15ht
            if somme15ht > 0:
                prob_over15_ht = round((1.0 / o15ht) / somme15ht, 4)

        prob_home = None
        prob_draw = None
        prob_away = None
        h = cotes.get("odds_home")
        d = cotes.get("odds_draw")
        a = cotes.get("odds_away")
        if h and d and a:
            total = 1/h + 1/d + 1/a
            prob_home = round((1/h) / total, 4)
            prob_draw = round((1/d) / total, 4)
            prob_away = round((1/a) / total, 4)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO odds (
                match_id, bookmaker, bookmaker_tier,
                collected_timestamp, hours_before_kickoff,
                odds_home, odds_draw, odds_away,
                prob_home_corrected, prob_draw_corrected, prob_away_corrected,
                odds_over15, odds_under15,
                odds_over25, odds_under25,
                odds_over35, odds_under35,
                odds_over45, odds_under45,
                odds_btts_yes, odds_btts_no,
                odds_over15_ht, odds_under15_ht,
                prob_over25_corrected, prob_btts_corrected,
                prob_over45_corrected, prob_over15_ht_corrected
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                match_id, "footystats", 2,
                maintenant, heures_avant,
                cotes.get("odds_home"), cotes.get("odds_draw"), cotes.get("odds_away"),
                prob_home, prob_draw, prob_away,
                cotes.get("odds_over15"), cotes.get("odds_under15"),
                cotes.get("odds_over25"), cotes.get("odds_under25"),
                cotes.get("odds_over35"), cotes.get("odds_under35"),
                cotes.get("odds_over45"), cotes.get("odds_under45"),
                cotes.get("odds_btts_yes"), cotes.get("odds_btts_no"),
                cotes.get("odds_over15_ht"), cotes.get("odds_under15_ht"),
                prob_over25, prob_btts,
                prob_over45, prob_over15_ht,
            ),
        )
        self.conn.commit()

    async def collecter_cotes_matchs_a_venir(self, heures: int = 720) -> dict:
        maintenant = int(time.time())
        limite = maintenant + (heures * 3600)

        matchs = self.conn.execute(
            """
            SELECT id, footystats_id, match_timestamp
            FROM matches
            WHERE status = 'upcoming'
            AND match_timestamp BETWEEN ? AND ?
            ORDER BY match_timestamp ASC
            """,
            (maintenant, limite),
        ).fetchall()

        logger.info_ctx(
            "Collecte cotes matchs a venir",
            context={"count": len(matchs)},
        )

        succes = 0
        echecs = 0
        for match in matchs:
            ok = await self.collecter_cotes_match(
                match_id=match["id"],
                footystats_match_id=match["footystats_id"],
            )
            if ok:
                succes += 1
            else:
                echecs += 1
            await asyncio.sleep(1)

        return {"total": len(matchs), "succes": succes, "echecs": echecs}

    async def fermer(self) -> None:
        await self.client.fermer()
