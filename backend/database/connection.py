"""
Connexion à la base de données SQLite.
Gestion du pool de connexions et des sessions.
"""

import sqlite3
import os
from typing import Generator
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def creer_connexion(
    database_path: str = None,
) -> sqlite3.Connection:
    """
    Crée une connexion SQLite avec les paramètres optimaux.
    """
    if database_path is None:
        database_path = settings.DATABASE_PATH

    os.makedirs(os.path.dirname(database_path), exist_ok=True)

    conn = sqlite3.connect(
        database_path,
        check_same_thread=False,
        timeout=60,
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")

    return conn


_connexion_globale: sqlite3.Connection = None


def obtenir_connexion() -> sqlite3.Connection:
    """
    Retourne la connexion globale.
    Crée la connexion si elle n'existe pas encore.
    """
    global _connexion_globale
    if _connexion_globale is None:
        _connexion_globale = creer_connexion()
        logger.info_ctx(
            "Connexion base de données établie",
            context={"path": settings.DATABASE_PATH},
        )
    return _connexion_globale


def fermer_connexion() -> None:
    """
    Ferme la connexion globale proprement.
    """
    global _connexion_globale
    if _connexion_globale is not None:
        _connexion_globale.close()
        _connexion_globale = None
        logger.info("Connexion base de données fermée")
