"""
Dependances FastAPI.
Authentication et acces base de donnees.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Header
from backend.core.config import settings
from backend.core.security import verifier_token_jwt, hasher_token
from backend.database.connection import obtenir_connexion
from backend.core.exceptions import (
    TokenInvalidException,
    TokenExpiredException,
)


def get_db() -> sqlite3.Connection:
    return obtenir_connexion()


def get_current_token(
    authorization: Optional[str] = Header(None),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    return authorization.replace("Bearer ", "")


def get_current_user(
    token: str = Depends(get_current_token),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        payload = verifier_token_jwt(token)
    except (TokenInvalidException, TokenExpiredException) as e:
        raise HTTPException(status_code=401, detail=e.message)

    user_id = payload.get("user_id")
    device_id = payload.get("device_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide")

    token_hash = hasher_token(token)
    session = conn.execute(
        """
        SELECT ut.*, ud.is_authorized as device_authorized
        FROM user_tokens ut
        LEFT JOIN user_devices ud ON ud.id = ut.device_id
        WHERE ut.user_id = ?
        AND ut.token_hash = ?
        ORDER BY ut.id DESC
        LIMIT 1
        """,
        (user_id, token_hash),
    ).fetchone()

    if not session:
        raise HTTPException(status_code=401, detail="Session invalide")

    if session["is_revoked"]:
        raise HTTPException(status_code=401, detail="Session révoquée")

    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.now(timezone.utc) >= expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=401, detail="Session expirée")

    if (
        device_id
        and session["device_id"]
        and session["device_id"] != device_id
    ):
        raise HTTPException(status_code=401, detail="Session invalide")

    if (
        session["device_id"]
        and session["device_authorized"] is not None
        and not session["device_authorized"]
    ):
        raise HTTPException(status_code=401, detail="Appareil non autorisé")

    user = conn.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    user_data = dict(user)
    user_data["is_admin"] = bool(
        user_data.get("is_admin", 0)
        or user_data["email"].lower() in settings.admin_emails
    )
    return user_data


def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Accès administrateur requis",
        )
    return current_user
