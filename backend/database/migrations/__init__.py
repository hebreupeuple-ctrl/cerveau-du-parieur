"""
Système de migrations de la base de données.
Chaque migration est versionnée et appliquée dans l'ordre.
"""

import sqlite3
from backend.core.logging import get_logger

logger = get_logger(__name__)


def obtenir_version(conn: sqlite3.Connection) -> int:
    """
    Retourne la version actuelle de la base de données.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL
                        DEFAULT (datetime('now')),
            description TEXT
        )
        """
    )
    conn.commit()

    cursor = conn.execute(
        "SELECT MAX(version) FROM schema_versions"
    )
    result = cursor.fetchone()[0]
    return result or 0


def enregistrer_version(
    conn: sqlite3.Connection,
    version: int,
    description: str,
) -> None:
    """
    Enregistre une migration comme appliquée.
    """
    conn.execute(
        """
        INSERT INTO schema_versions (version, description)
        VALUES (?, ?)
        """,
        (version, description),
    )
    conn.commit()


def appliquer_migrations(
    conn: sqlite3.Connection = None,
) -> None:
    """
    Applique toutes les migrations manquantes.
    """
    from backend.database.connection import obtenir_connexion
    from backend.database.migrations.migration_001 import (
        appliquer as migration_001,
        DESCRIPTION as DESC_001,
    )
    from backend.database.migrations.migration_002 import (
        appliquer as migration_002,
        DESCRIPTION as DESC_002,
    )

    if conn is None:
        conn = obtenir_connexion()

    version_actuelle = obtenir_version(conn)
    logger.info_ctx(
        "Vérification des migrations",
        context={"version_actuelle": version_actuelle},
    )

    migrations = [
        (1, migration_001, DESC_001),
        (2, migration_002, DESC_002),
    ]

    for version, migration_fn, description in migrations:
        if version > version_actuelle:
            logger.info_ctx(
                f"Application migration {version}",
                context={"description": description},
            )
            migration_fn(conn)
            enregistrer_version(conn, version, description)
            logger.info_ctx(
                f"Migration {version} appliquée",
                context={"description": description},
            )

    logger.info("Toutes les migrations sont à jour")
