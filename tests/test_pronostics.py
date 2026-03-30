"""
Tests endpoints pronostics :
- Place un pari → bankroll diminue
- Résout won/lost → bankroll mise à jour correctement
- Bankroll ne peut pas devenir négative
- Historique pagine et filtre correctement
"""
import time
import pytest
from tests.conftest import creer_utilisateur, creer_token, auth_headers


def _inserer_match_futur(db):
    lid = db.execute(
        """INSERT INTO leagues (name, country, footystats_id, is_active)
           VALUES ('Ligue1', 'France', 10, 1)"""
    ).lastrowid
    t1 = db.execute(
        "INSERT INTO teams (name, country, footystats_id) VALUES ('PSG', 'France', 100)"
    ).lastrowid
    t2 = db.execute(
        "INSERT INTO teams (name, country, footystats_id) VALUES ('OM', 'France', 101)"
    ).lastrowid
    sid = db.execute(
        """INSERT INTO seasons (footystats_id, league_id, name, year, start_date, end_date)
           VALUES (10, ?, '2024', 2024, '2024-08-01', '2025-05-31')""",
        (lid,),
    ).lastrowid
    db.commit()
    ts_futur = int(time.time()) + 86400
    mid = db.execute(
        """
        INSERT INTO matches (footystats_id, season_id, league_id, home_team_id, away_team_id,
                             match_date, match_timestamp, status)
        VALUES (1001, ?, ?, ?, ?, '2026-04-01', ?, 'upcoming')
        """,
        (sid, lid, t1, t2, ts_futur),
    ).lastrowid
    db.commit()
    return mid


def _inserer_pronostic_pending(db, user_id, match_id):
    pid = db.execute(
        """
        INSERT INTO pronostics (
            user_id, match_id, market,
            model_probability, bookmaker_probability, probability_edge,
            expected_value, confidence_score, reference_bookmaker,
            reference_odds, kelly_fraction_used, kelly_raw,
            recommended_stake, bankroll_at_recommendation, status
        ) VALUES (?, ?, 'over25', 0.65, 0.55, 0.10, 0.15, 0.70, 'bet365',
                  2.10, 0.125, 0.05, 15.0, 200.0, 'pending')
        """,
        (user_id, match_id),
    ).lastrowid
    db.commit()
    return pid


# ─────────────────────────────────────────────
# Test : place un pari
# ─────────────────────────────────────────────

def test_placer_pari_reduit_bankroll(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    res = client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 20.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["new_bankroll"] == pytest.approx(180.0, abs=0.01)


def test_placer_pari_bankroll_insuffisante(db, client):
    uid = creer_utilisateur(db, bankroll=5.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    res = client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 50.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    assert res.status_code == 409
    body = res.json()
    assert body["success"] is False
    assert "message" in body["error"]


def test_placer_pari_deja_place(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 10.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    # Tentative de double placement
    res = client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 10.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    assert res.status_code == 409


# ─────────────────────────────────────────────
# Test : résoudre un pari
# ─────────────────────────────────────────────

def test_resoudre_gagne_augmente_bankroll(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 20.0, "actual_odds": 2.5},
        headers=auth_headers(token),
    )
    # bankroll = 180 après placement
    res = client.post(
        f"/api/v1/pronostics/{pid}/resolve",
        json={"result": "won"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    # profit = 20 * (2.5-1) = 30 → bankroll = 180 + 20 + 30 = 230
    assert data["new_bankroll"] == pytest.approx(230.0, abs=0.01)
    assert data["profit"] == pytest.approx(30.0, abs=0.01)


def test_resoudre_perdu_bankroll_inchangee_par_rapport_post_placement(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 20.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    res = client.post(
        f"/api/v1/pronostics/{pid}/resolve",
        json={"result": "lost"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    # mise perdue, retour = 0, bankroll reste à 180
    assert data["new_bankroll"] == pytest.approx(180.0, abs=0.01)
    assert data["profit"] == pytest.approx(-20.0, abs=0.01)


def test_resoudre_void_rembourse_la_mise(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    client.post(
        f"/api/v1/pronostics/{pid}/place",
        json={"actual_stake": 20.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    res = client.post(
        f"/api/v1/pronostics/{pid}/resolve",
        json={"result": "void"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["new_bankroll"] == pytest.approx(200.0, abs=0.01)


# ─────────────────────────────────────────────
# Test : historique
# ─────────────────────────────────────────────

def test_historique_retourne_items(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    pid = _inserer_pronostic_pending(db, uid, mid)

    res = client.get("/api/v1/pronostics/history", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()["data"]
    assert "items" in data
    assert "stats" in data
    assert "pagination" in data
    assert len(data["items"]) >= 1


def test_historique_filtre_en_cours(db, client):
    uid = creer_utilisateur(db, bankroll=200.0)
    token = creer_token(db, uid)
    mid = _inserer_match_futur(db)
    _inserer_pronostic_pending(db, uid, mid)

    res = client.get(
        "/api/v1/pronostics/history?status=en_cours",
        headers=auth_headers(token),
    )
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    for item in items:
        assert item["status"] in ("pending", "placed")
