"""
Tests format d'erreur unifié.
- Toutes les HTTPException retournent {"success": false, "error": {"code": ..., "message": ...}}
- Plus jamais {"detail": "..."} côté client
"""
from tests.conftest import creer_utilisateur, creer_token, auth_headers


def test_login_mauvais_mdp_retourne_format_unifie(db, client):
    creer_utilisateur(db, email="user@test.com", password="bonmdp123")

    res = client.post("/api/v1/auth/login", json={
        "email": "user@test.com",
        "password": "mauvaismdp",
    })
    assert res.status_code == 401
    body = res.json()
    assert body["success"] is False
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert isinstance(body["error"]["message"], str)
    assert len(body["error"]["message"]) > 0


def test_register_email_deja_utilise_retourne_format_unifie(db, client):
    creer_utilisateur(db, email="dup@test.com")

    res = client.post("/api/v1/auth/register", json={
        "email": "dup@test.com",
        "password": "password123",
    })
    assert res.status_code == 409
    body = res.json()
    assert body["success"] is False
    assert "error" in body
    assert isinstance(body["error"]["message"], str)


def test_token_manquant_retourne_format_unifie(db, client):
    res = client.get("/api/v1/pronostics/today")
    assert res.status_code == 401
    body = res.json()
    assert body["success"] is False
    assert "error" in body


def test_admin_requis_retourne_format_unifie(db, client):
    uid = creer_utilisateur(db, is_admin=0)
    token = creer_token(db, uid)

    res = client.post("/api/v1/system/manual-sync", headers=auth_headers(token))
    assert res.status_code == 403
    body = res.json()
    assert body["success"] is False
    assert "error" in body
    assert "message" in body["error"]


def test_pronostic_introuvable_retourne_format_unifie(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)

    res = client.post(
        "/api/v1/pronostics/99999/place",
        json={"actual_stake": 10.0, "actual_odds": 2.0},
        headers=auth_headers(token),
    )
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert "error" in body
    assert "message" in body["error"]


def test_logout_retourne_200(db, client):
    uid = creer_utilisateur(db)
    token = creer_token(db, uid)

    res = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["logged_out"] is True
