"""
Fixtures partagées pour les tests.
"""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.api.router import creer_app
from backend.database.migrations import appliquer_migrations
from backend.core.security import hasher_mot_de_passe, creer_token_jwt, hasher_token
from datetime import datetime, timezone, timedelta


@pytest.fixture(scope="function")
def db():
    """Base de données SQLite en mémoire pour les tests."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    appliquer_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def client(db):
    """TestClient FastAPI avec override de la connexion DB."""
    from backend.api.dependencies import get_db
    from backend.api.router import creer_app

    app = creer_app()
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def creer_utilisateur(db, email="test@example.com", password="password123",
                       bankroll=200.0, is_admin=0):
    """Insère un utilisateur de test et retourne son id."""
    cursor = db.execute(
        """
        INSERT INTO users (email, password_hash, initial_bankroll, current_bankroll,
                           kelly_fraction, is_admin)
        VALUES (?, ?, ?, ?, 0.125, ?)
        """,
        (email, hasher_mot_de_passe(password), bankroll, bankroll, is_admin),
    )
    db.commit()
    return cursor.lastrowid


def creer_token(db, user_id, device_id=1):
    """Crée un token JWT valide pour l'utilisateur."""
    # Assure que le device existe
    db.execute(
        """
        INSERT OR IGNORE INTO user_devices
            (id, user_id, device_fingerprint, device_name, platform, is_authorized)
        VALUES (?, ?, 'test-device', 'Test', 'web', 1)
        """,
        (device_id, user_id),
    )
    token = creer_token_jwt(user_id=user_id, device_id=device_id)
    token_hash = hasher_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    db.execute(
        "INSERT INTO user_tokens (user_id, token_hash, device_id, expires_at) VALUES (?,?,?,?)",
        (user_id, token_hash, device_id, expires_at),
    )
    db.commit()
    return token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
