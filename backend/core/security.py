"""
Securite centrale du systeme.
JWT, hachage des mots de passe, chiffrement AES-256.
"""

import logging
import os
import secrets
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from backend.core.config import settings
from backend.core.exceptions import (
    TokenExpiredException,
    TokenInvalidException,
)

logger = logging.getLogger(__name__)


def hasher_mot_de_passe(mot_de_passe: str) -> str:
    """Hache un mot de passe avec bcrypt."""
    mot_de_passe_bytes = mot_de_passe[:72].encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(mot_de_passe_bytes, salt)
    return hashed.decode("utf-8")


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    """Verifie un mot de passe contre son hash bcrypt."""
    try:
        mot_de_passe_bytes = mot_de_passe[:72].encode("utf-8")
        hash_bytes = hash_stocke.encode("utf-8")
        return bcrypt.checkpw(mot_de_passe_bytes, hash_bytes)
    except Exception:
        return False


def creer_token_jwt(
    user_id: int,
    device_id: Optional[int] = None,
    expire_heures: int = None,
) -> str:
    """Cree un token JWT signe."""
    if expire_heures is None:
        expire_heures = settings.JWT_EXPIRE_HOURS

    expire = datetime.now(timezone.utc) + timedelta(hours=expire_heures)

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
    """Verifie et decode un token JWT."""
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
    """Chiffre une donnee sensible."""
    if not settings.ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY non configurée — donnée stockée en clair")
        return donnee
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cle = bytes.fromhex(settings.ENCRYPTION_KEY)
        aesgcm = AESGCM(cle)
        nonce = os.urandom(12)
        donnee_bytes = donnee.encode("utf-8")
        chiffree = aesgcm.encrypt(nonce, donnee_bytes, None)
        return (nonce + chiffree).hex()
    except Exception:
        logger.error("Echec du chiffrement AES-GCM — donnée stockée en clair", exc_info=True)
        return donnee


def dechiffrer_donnee(donnee_chiffree: str) -> str:
    """Dechiffre une donnee chiffree."""
    if not settings.ENCRYPTION_KEY:
        return donnee_chiffree
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cle = bytes.fromhex(settings.ENCRYPTION_KEY)
        aesgcm = AESGCM(cle)
        donnee_bytes = bytes.fromhex(donnee_chiffree)
        nonce = donnee_bytes[:12]
        chiffree = donnee_bytes[12:]
        return aesgcm.decrypt(nonce, chiffree, None).decode("utf-8")
    except Exception:
        logger.error("Echec du déchiffrement AES-GCM — donnée retournée telle quelle", exc_info=True)
        return donnee_chiffree


def generer_token_reset() -> tuple[str, str]:
    """Genere un token de reinitialisation."""
    token_brut = secrets.token_urlsafe(32)
    token_hashe = hashlib.sha256(token_brut.encode()).hexdigest()
    return token_brut, token_hashe


def hasher_token(token: str) -> str:
    """Hache un token avec SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()
