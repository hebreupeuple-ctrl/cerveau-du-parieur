"""
Endpoints d'authentification.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
import sqlite3

from backend.api.dependencies import get_db, get_current_token, get_current_user
from backend.core.security import (
    hasher_mot_de_passe,
    verifier_mot_de_passe,
    creer_token_jwt,
    hasher_token,
)
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.constants import MARKETS

logger = get_logger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    initial_bankroll: float = Field(default=150.0, gt=0)
    kelly_fraction: float = Field(default=0.125, gt=0, le=1)


class UpdateProfileRequest(BaseModel):
    kelly_fraction: float = Field(gt=0, le=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fingerprint: str = "default"
    device_name: str = "Mon appareil"
    platform: str = "web"


def reponse_succes(data: dict, status_code: int = 200):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0"
            }
        }
    )


@router.post("/register")
async def register(req: RegisterRequest, conn: sqlite3.Connection = Depends(get_db)):
    existant = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (req.email,),
    ).fetchone()

    if existant:
        raise HTTPException(
            status_code=409,
            detail={"code": "RESOURCE_ALREADY_EXISTS", "message": "Email déjà utilisé"}
        )

    password_hash = hasher_mot_de_passe(req.password)
    is_first_user = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0] == 0
    is_admin = int(
        is_first_user
        or req.email.lower() in settings.admin_emails
    )

    cursor = conn.execute(
        """
        INSERT INTO users (
            email, password_hash,
            initial_bankroll, current_bankroll,
            kelly_fraction, is_admin
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            req.email, password_hash,
            req.initial_bankroll, req.initial_bankroll,
            req.kelly_fraction,
            is_admin,
        ),
    )
    conn.commit()
    user_id = cursor.lastrowid

    for market in MARKETS[:7]:
        conn.execute(
            "INSERT OR IGNORE INTO user_markets (user_id, market) VALUES (?, ?)",
            (user_id, market),
        )

    ligues = conn.execute(
        "SELECT id FROM leagues WHERE is_active = 1"
    ).fetchall()
    if not ligues:
        ligues = conn.execute(
            "SELECT id FROM leagues"
        ).fetchall()

    for ligue in ligues:
        conn.execute(
            "INSERT OR IGNORE INTO user_leagues (user_id, league_id) VALUES (?, ?)",
            (user_id, ligue["id"]),
        )
    conn.commit()

    logger.info_ctx("Nouvel utilisateur créé", context={"user_id": user_id})

    return reponse_succes(
        {"user_id": user_id, "email": req.email, "onboarding_completed": False},
        status_code=201
    )


@router.post("/login")
async def login(req: LoginRequest, conn: sqlite3.Connection = Depends(get_db)):
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (req.email,),
    ).fetchone()

    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_INVALID_CREDENTIALS", "message": "Email ou mot de passe incorrect"}
        )

    if user["locked_until"]:
        locked_until = datetime.fromisoformat(user["locked_until"])
        if datetime.now(timezone.utc) < locked_until.replace(tzinfo=timezone.utc):
            raise HTTPException(
                status_code=403,
                detail={"code": "AUTH_ACCOUNT_LOCKED", "message": "Compte verrouillé"}
            )

    if not verifier_mot_de_passe(req.password, user["password_hash"]):
        attempts = user["failed_login_attempts"] + 1
        locked_until = None

        if attempts >= 5:
            locked_until = (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat()

        conn.execute(
            """
            UPDATE users SET
                failed_login_attempts = ?,
                locked_until = ?
            WHERE id = ?
            """,
            (attempts, locked_until, user["id"]),
        )
        conn.commit()

        if locked_until:
            raise HTTPException(
                status_code=403,
                detail={"code": "AUTH_ACCOUNT_LOCKED", "message": "Compte verrouillé après trop de tentatives"}
            )

        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_INVALID_CREDENTIALS", "message": "Email ou mot de passe incorrect"}
        )

    conn.execute(
        """
        UPDATE users SET
            failed_login_attempts = 0,
            locked_until = NULL,
            last_login_at = datetime('now')
        WHERE id = ?
        """,
        (user["id"],),
    )

    device = conn.execute(
        "SELECT * FROM user_devices WHERE user_id = ? AND device_fingerprint = ?",
        (user["id"], req.device_fingerprint),
    ).fetchone()

    device_id = None
    if not device:
        cursor = conn.execute(
            """
            INSERT INTO user_devices (
                user_id, device_fingerprint, device_name,
                platform, is_authorized, authorized_at, last_seen_at
            ) VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
            """,
            (user["id"], req.device_fingerprint, req.device_name, req.platform),
        )
        device_id = cursor.lastrowid
    else:
        device_id = device["id"]
        conn.execute(
            "UPDATE user_devices SET last_seen_at = datetime('now') WHERE id = ?",
            (device_id,),
        )

    conn.commit()

    token = creer_token_jwt(user_id=user["id"], device_id=device_id)
    token_hash = hasher_token(token)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    ).isoformat()

    conn.execute(
        """
        INSERT INTO user_tokens (user_id, token_hash, device_id, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (user["id"], token_hash, device_id, expires_at),
    )
    conn.commit()

    return reponse_succes({
        "access_token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "device_authorized": True,
        "requires_device_verification": False,
    })


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return reponse_succes({
        "id": current_user["id"],
        "email": current_user["email"],
        "is_admin": bool(current_user.get("is_admin")),
        "initial_bankroll": current_user["initial_bankroll"],
        "current_bankroll": current_user["current_bankroll"],
        "kelly_fraction": current_user["kelly_fraction"],
        "min_confidence_simple": current_user["min_confidence_simple"],
        "system_mode": current_user["system_mode"],
        "onboarding_completed": bool(current_user["onboarding_completed"]),
    })


@router.put("/me")
async def update_me(
    req: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    conn.execute(
        "UPDATE users SET kelly_fraction = ? WHERE id = ?",
        (req.kelly_fraction, current_user["id"]),
    )
    conn.commit()
    return reponse_succes({"kelly_fraction": req.kelly_fraction})


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    current_token: str = Depends(get_current_token),
    conn: sqlite3.Connection = Depends(get_db),
):
    token_hash = hasher_token(current_token)
    conn.execute(
        """
        UPDATE user_tokens
        SET is_revoked = 1
        WHERE user_id = ?
        AND token_hash = ?
        """,
        (current_user["id"], token_hash),
    )
    conn.commit()
    return reponse_succes({"logged_out": True})
