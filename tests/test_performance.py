"""
Tests endpoint /performance/summary
- total_profit inclut gains ET pertes
- filtre period (week / month / all) fonctionne
"""
import time
from datetime import datetime, timezone, timedelta
from tests.conftest import creer_utilisateur, creer_token, auth_headers


def _inserer_pronostic_resolu(db, user_id, match_id, market, stake, odds, result,
                               placed_days_ago=1):
    """
    Insère un pronostic dans l'état résolu pour les tests.
    placed_days_ago : combien de jours dans le passé a-t-il été placé.
    """
    if result == "won":
        profit = round(stake * (odds - 1.0), 2)
        retour = round(stake + profit, 2)
    elif result == "lost":
        profit = -stake
        retour = 0.0
    else:
        profit = 0.0
        retour = stake

    placed_at = (
        datetime.now(timezone.utc) - timedelta(days=placed_days_ago)
    ).strftime("%Y-%m-%d %H:%M:%S")

    cursor = db.execute(
        """
        INSERT INTO pronostics (
            user_id, match_id, market,
            model_probability, bookmaker_probability, probability_edge,
            expected_value, confidence_score, reference_bookmaker,
            reference_odds, kelly_fraction_used, kelly_raw,
            recommended_stake, bankroll_at_recommendation,
            status, actual_stake, actual_odds, actual_profit,
            placed_at, resolved_at
        ) VALUES (?, ?, ?, 0.6, 0.5, 0.1, 0.1, 0.7, 'bet365',
                  ?, 0.125, 0.05, ?, 200.0, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, match_id, market, odds, stake,
         result, stake, odds, profit, placed_at, placed_at),
    )
    db.commit()
    return cursor.lastrowid


def _inserer_match(db, league_id=1):
    """Insère un match minimal et retourne son id."""
    ts = int(time.time()) - 7200
    t1 = db.execute(
        "INSERT INTO teams (name, country, footystats_id) VALUES ('Home', 'France', 1)"
    ).lastrowid
    t2 = db.execute(
        "INSERT INTO teams (name, country, footystats_id) VALUES ('Away', 'France', 2)"
    ).lastrowid
    sid = db.execute(
        """INSERT INTO seasons (footystats_id, league_id, name, year, start_date, end_date)
           VALUES (1, ?, '2024', 2024, '2024-08-01', '2025-05-31')""",
        (league_id,),
    ).lastrowid
    db.commit()
    mid = db.execute(
        """
        INSERT INTO matches (footystats_id, season_id, league_id, home_team_id, away_team_id,
                             match_date, match_timestamp, status, home_goals, away_goals)
        VALUES (999, ?, ?, ?, ?, '2024-01-01', ?, 'complete', 2, 1)
        """,
        (sid, league_id, t1, t2, ts),
    ).lastrowid
    db.commit()
    return mid


def _inserer_ligue(db):
    lid = db.execute(
        """INSERT INTO leagues (name, country, footystats_id, is_active)
           VALUES ('TestLeague', 'France', 1, 1)"""
    ).lastrowid
    db.commit()
    return lid


# ─────────────────────────────────────────────
# Test 1 : total_profit inclut les pertes
# ─────────────────────────────────────────────

def test_total_profit_inclut_les_pertes(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)
    lid = _inserer_ligue(db)
    mid = _inserer_match(db, lid)

    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0, result="won")
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0, result="lost")

    res = client.get("/api/v1/performance/summary", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    data = res.json()["data"]

    # won : +10€ de profit, lost : -10€ → profit net = 0
    assert data["volume"]["total_profit"] == pytest.approx(0.0, abs=0.01)


def test_total_profit_gagnant_uniquement(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)
    lid = _inserer_ligue(db)
    mid = _inserer_match(db, lid)

    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.5, result="won")

    res = client.get("/api/v1/performance/summary", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    # profit = 10 * (2.5 - 1) = 15
    assert data["volume"]["total_profit"] == pytest.approx(15.0, abs=0.01)


def test_total_profit_perdant_uniquement(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)
    lid = _inserer_ligue(db)
    mid = _inserer_match(db, lid)

    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=20.0, odds=1.8, result="lost")

    res = client.get("/api/v1/performance/summary", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["volume"]["total_profit"] == pytest.approx(-20.0, abs=0.01)


# ─────────────────────────────────────────────
# Test 2 : filtre period fonctionne
# ─────────────────────────────────────────────

def test_period_all_retourne_tout(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)
    lid = _inserer_ligue(db)
    mid = _inserer_match(db, lid)

    # Pari vieux (15 jours)
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0,
                               result="won", placed_days_ago=15)
    # Pari récent (2 jours)
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0,
                               result="won", placed_days_ago=2)

    res = client.get("/api/v1/performance/summary?period=all", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json()["data"]["volume"]["total_bets"] == 2


def test_period_week_exclut_vieux_paris(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)
    lid = _inserer_ligue(db)
    mid = _inserer_match(db, lid)

    # Pari vieux de 15 jours → hors de la semaine
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0,
                               result="won", placed_days_ago=15)
    # Pari récent (2 jours) → dans la semaine
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0,
                               result="won", placed_days_ago=2)

    res = client.get("/api/v1/performance/summary?period=week", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json()["data"]["volume"]["total_bets"] == 1


def test_period_month_exclut_tres_vieux_paris(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)
    lid = _inserer_ligue(db)
    mid = _inserer_match(db, lid)

    # Pari vieux de 45 jours → hors du mois
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0,
                               result="won", placed_days_ago=45)
    # Pari récent (10 jours) → dans le mois
    _inserer_pronostic_resolu(db, uid, mid, "over25", stake=10.0, odds=2.0,
                               result="won", placed_days_ago=10)

    res = client.get("/api/v1/performance/summary?period=month", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json()["data"]["volume"]["total_bets"] == 1


import pytest
