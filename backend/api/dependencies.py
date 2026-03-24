"""
Dependances FastAPI.
Authentication et acces base de donnees.
"""

import sqlite3
from typing import Optional
from fastapi import Depends, HTTPException, Header
from backend.core.security import verifier_token_jwt
from backend.database.connection import obtenir_connexion
from backend.core.exceptions import (
    TokenInvalidException,
    TokenExpiredException,
)


def get_db() -> sqlite3.Connection:
    return obtenir_connexion()


def get_current_user(
    authorization: Optional[str] = Header(None),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.replace("Bearer ", "")

    try:
        payload = verifier_token_jwt(token)
    except (TokenInvalidException, TokenExpiredException) as e:
        raise HTTPException(status_code=401, detail=e.message)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = conn.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    return dict(user)
