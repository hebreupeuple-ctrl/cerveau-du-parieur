"""
Sécurité centrale du système.
JWT, hachage des mots de passe, chiffrement AES-256.
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from backend.core.config import settings
from backend.core.exceptions import (
    TokenExpiredException,
    TokenInvalidException,
)

# Contexte bcrypt pour les mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hasher_mot_de_passe(mot_de_passe: str) -> str:
    """
    Hache un mot de passe avec bcrypt.
    Le salt est généré automatiquement.
    """
    return pwd_context.hash(mot_de_passe)


def verifier_mot_de_passe(
    mot_de_passe: str,
    hash_stocke: str,
) -> bool:
    """
    Vérifie un mot de passe contre son hash bcrypt.
    """
    return pwd_context.verify(mot_de_passe, hash_stocke)


def creer_token_jwt(
    user_id: int,
    device_id: Optional[int] = None,
    expire_heures: int = None,
) -> str:
    """
    Crée un token JWT signé.
    """
    if expire_heures is None:
        expire_heures = settings.JWT_EXPIRE_HOURS

    expire = datetime.now(timezone.utc) + timedelta(
        hours=expire_heures
    )

    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "device_id": device_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verifier_token_jwt(token: str) -> dict:
    """
    Vérifie et décode un token JWT.
    Lève une exception si invalide ou expiré.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException()
    except JWTError:
        raise TokenInvalidException()


def chiffrer_donnee(donnee: str) -> str:
    """
    Chiffre une donnée sensible avec AES-256-GCM.
    Retourne la donnée chiffrée en hexadécimal.
    """
    if not settings.ENCRYPTION_KEY:
        return donnee

    cle = bytes.fromhex(settings.ENCRYPTION_KEY)
    aesgcm = AESGCM(cle)
    nonce = os.urandom(12)
    donnee_bytes = donnee.encode("utf-8")
    chiffree = aesgcm.encrypt(nonce, donnee_bytes, None)
    return (nonce + chiffree).hex()


def dechiffrer_donnee(donnee_chiffree: str) -> str:
    """
    Déchiffre une donnée chiffrée avec AES-256-GCM.
    """
    if not settings.ENCRYPTION_KEY:
        return donnee_chiffree

    cle = bytes.fromhex(settings.ENCRYPTION_KEY)
    aesgcm = AESGCM(cle)
    donnee_bytes = bytes.fromhex(donnee_chiffree)
    nonce = donnee_bytes[:12]
    chiffree = donnee_bytes[12:]
    return aesgcm.decrypt(nonce, chiffree, None).decode("utf-8")


def generer_token_reset() -> tuple[str, str]:
    """
    Génère un token de réinitialisation de mot de passe.
    Retourne (token_brut, token_hashé).
    Le token brut est envoyé par email.
    Le token hashé est stocké en base.
    """
    token_brut = secrets.token_urlsafe(32)
    token_hashe = hashlib.sha256(
        token_brut.encode()
    ).hexdigest()
    return token_brut, token_hashe


def hasher_token(token: str) -> str:
    """
    Hache un token avec SHA-256.
    Utilisé pour stocker les tokens en base.
    """
    return hashlib.sha256(token.encode()).hexdigest()
