import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from backend.core.config import settings
from backend.data.footystats.parsers.leagues import (
    extraire_id_ligue,
    extraire_nom_ligue,
    extraire_saison_principale,
    parser_ligue,
)
from backend.data.sync import synchroniser_ligues
from backend.database.connection import fermer_connexion, obtenir_connexion
from backend.database.migrations import appliquer_migrations


class FootyStatsLeagueParsingTests(unittest.TestCase):
    def test_parser_ligue_supporte_liste_de_saisons(self):
        ligue = parser_ligue({
            "id": 10,
            "name": "England Premier League",
            "country": "England",
            "season": [
                {"id": 100, "year": 20242025, "name": "2024/2025"},
                {"id": 101, "year": 20252026, "name": "2025/2026"},
            ],
        })

        self.assertIsNotNone(ligue)
        self.assertEqual(ligue["season_id"], 101)
        self.assertEqual(ligue["season_name"], "2025/2026")
        self.assertEqual(ligue["season_year"], 2025)

    def test_parser_ligue_supporte_objet_saison_unique(self):
        ligue = parser_ligue({
            "id": 20,
            "name": "France Ligue 1",
            "country": "France",
            "season": {"id": 201, "name": "2025/2026"},
        })

        self.assertIsNotNone(ligue)
        self.assertEqual(ligue["season_id"], 201)
        self.assertEqual(ligue["season_name"], "2025/2026")
        self.assertEqual(ligue["season_year"], 2025)

    def test_parser_ligue_genere_un_id_stable_si_ligue_sans_id(self):
        payload = {
            "name": "Bundesliga",
            "country": "Germany",
            "season": [{"id": 14968, "year": 20252026}],
        }

        ligue = parser_ligue(payload)

        self.assertIsNotNone(ligue)
        self.assertIsInstance(ligue["footystats_id"], int)
        self.assertGreater(ligue["footystats_id"], 0)
        self.assertEqual(ligue["name"], "Germany Bundesliga")

    def test_parser_ligue_supporte_enveloppe_data(self):
        saison = extraire_saison_principale({
            "id": 30,
            "name": "Spain La Liga",
            "country": "Spain",
            "season": {
                "data": [
                    {"id": 301, "year": 20242025},
                    {"id": 302, "name": "2025/2026"},
                ]
            },
        })

        self.assertIsNotNone(saison)
        self.assertEqual(saison["id"], 302)
        self.assertEqual(saison["name"], "2025/2026")
        self.assertEqual(saison["year"], 2025)

    def test_extraire_id_ligue_prend_competition_id_quand_disponible(self):
        league_id = extraire_id_ligue({
            "competition_id": 777,
            "league_name": "Bundesliga",
            "country": "Germany",
        })
        self.assertEqual(league_id, 777)

    def test_extraire_nom_ligue_prefixe_le_pays_si_necessaire(self):
        nom = extraire_nom_ligue({
            "league_name": "Bundesliga",
            "country": "Germany",
        })
        self.assertEqual(nom, "Germany Bundesliga")


class SyncLeagueParsingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_database_path = settings.DATABASE_PATH
        self.original_database_url = settings.DATABASE_URL

        settings.DATABASE_PATH = os.path.join(self.tempdir.name, "test.db")
        settings.DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"

        fermer_connexion()
        conn = obtenir_connexion()
        appliquer_migrations(conn)

    def tearDown(self):
        fermer_connexion()
        settings.DATABASE_PATH = self.original_database_path
        settings.DATABASE_URL = self.original_database_url
        self.tempdir.cleanup()

    def test_synchroniser_ligues_supporte_saison_objet(self):
        payload = {
            "data": [
                {
                    "id": 501,
                    "name": "Test League",
                    "country": "Testland",
                    "season": {"id": 9001, "name": "2025/2026"},
                }
            ]
        }

        with patch(
            "backend.data.sync.FootyStatsClient.get",
            new=AsyncMock(return_value=payload),
        ):
            conn = obtenir_connexion()
            resultat = asyncio.run(synchroniser_ligues(conn))

        self.assertEqual(resultat["total_footystats"], 1)
        self.assertEqual(resultat["ajoutees"], 1)
        self.assertTrue(resultat["catalogue_changed"])
        self.assertEqual(resultat["total_actives_db"], 1)

    def test_synchroniser_ligues_supporte_ligue_sans_id_top_level(self):
        payload = {
            "data": [
                {
                    "name": "Bundesliga",
                    "country": "Germany",
                    "season": [{"id": 14968, "year": 20252026}],
                }
            ]
        }

        with patch(
            "backend.data.sync.FootyStatsClient.get",
            new=AsyncMock(return_value=payload),
        ):
            conn = obtenir_connexion()
            resultat = asyncio.run(synchroniser_ligues(conn))

        row = obtenir_connexion().execute(
            "SELECT footystats_id, name, is_active FROM leagues WHERE name = ?",
            ("Germany Bundesliga",),
        ).fetchone()

        self.assertEqual(resultat["total_footystats"], 1)
        self.assertEqual(resultat["ajoutees"], 1)
        self.assertTrue(resultat["catalogue_changed"])
        self.assertIsNotNone(row)
        self.assertGreater(row["footystats_id"], 0)
        self.assertEqual(row["is_active"], 1)
