import time
from unittest.mock import patch

from backend.scheduler.tasks.automation import _mettre_a_jour_clv_sync
from tests.conftest import creer_utilisateur


def test_mettre_a_jour_clv_capture_la_cote_de_fermeture(db):
    class ConnectionProxy:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    user_id = creer_utilisateur(db, email="clv@example.com")

    league_id = db.execute(
        """
        INSERT INTO leagues (name, country, footystats_id, is_active)
        VALUES ('Test League', 'France', 501, 1)
        """
    ).lastrowid
    home_team_id = db.execute(
        "INSERT INTO teams (name, country, footystats_id) VALUES ('Home', 'France', 601)"
    ).lastrowid
    away_team_id = db.execute(
        "INSERT INTO teams (name, country, footystats_id) VALUES ('Away', 'France', 602)"
    ).lastrowid
    season_id = db.execute(
        """
        INSERT INTO seasons (footystats_id, league_id, name, year, start_date, end_date)
        VALUES (701, ?, '2026', 2026, '2026-01-01', '2026-12-31')
        """,
        (league_id,),
    ).lastrowid

    kickoff = int(time.time()) + 1800
    match_id = db.execute(
        """
        INSERT INTO matches (
            footystats_id, season_id, league_id, home_team_id, away_team_id,
            match_date, match_timestamp, status
        ) VALUES (801, ?, ?, ?, ?, '2026-03-31', ?, 'upcoming')
        """,
        (season_id, league_id, home_team_id, away_team_id, kickoff),
    ).lastrowid

    db.execute(
        """
        INSERT INTO odds (
            match_id, bookmaker, bookmaker_tier, collected_timestamp, odds_over25
        ) VALUES (?, 'bet365', 1, ?, 1.9)
        """,
        (match_id, int(time.time())),
    )

    pronostic_id = db.execute(
        """
        INSERT INTO pronostics (
            user_id, match_id, market,
            model_probability, bookmaker_probability, probability_edge,
            expected_value, reference_bookmaker, reference_odds,
            confidence_score, kelly_fraction_used, kelly_raw,
            recommended_stake, bankroll_at_recommendation,
            status, actual_stake, actual_odds
        ) VALUES (?, ?, 'over25', 0.64, 0.53, 0.11, 0.14, 'bet365', 2.1,
                  0.74, 0.125, 0.05, 15.0, 200.0, 'placed', 10.0, 2.1)
        """,
        (user_id, match_id),
    ).lastrowid
    db.commit()

    with patch(
        "backend.scheduler.tasks.automation.creer_connexion",
        return_value=ConnectionProxy(db),
    ):
        resultat = _mettre_a_jour_clv_sync()

    row = db.execute(
        "SELECT closing_odds, clv FROM pronostics WHERE id = ?",
        (pronostic_id,),
    ).fetchone()

    assert resultat["mis_a_jour"] == 1
    assert row["closing_odds"] == 1.9
    assert row["clv"] == 10.53
