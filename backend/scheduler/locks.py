"""
Verrous distribués simples pour les jobs système.
"""

import os
import secrets
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.connection import creer_connexion

logger = get_logger(__name__)


class DistributedJobLockService:
    def __init__(
        self,
        owner_id: Optional[str] = None,
        lease_seconds: Optional[int] = None,
    ):
        self.owner_id = owner_id or f"{socket.gethostname()}:{os.getpid()}"
        self.lease_seconds = lease_seconds or (
            settings.SYSTEM_JOB_LOCK_LEASE_MINUTES * 60
        )

    def acquire(self, job_name: str) -> Optional[str]:
        # Nettoyage opportuniste des locks expirés d'autres jobs
        self.cleanup_expired_locks()

        token = secrets.token_hex(16)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.lease_seconds)
        conn = creer_connexion()

        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT lock_token, lock_expires_at
                FROM scheduler_locks
                WHERE job_name = ?
                """,
                (job_name,),
            ).fetchone()

            if row:
                lock_expires_at = datetime.fromisoformat(
                    row["lock_expires_at"]
                )
                if lock_expires_at > now:
                    conn.rollback()
                    return None

                conn.execute(
                    """
                    UPDATE scheduler_locks SET
                        lock_token = ?,
                        owner_id = ?,
                        acquired_at = ?,
                        lock_expires_at = ?,
                        updated_at = datetime('now')
                    WHERE job_name = ?
                    """,
                    (
                        token,
                        self.owner_id,
                        now.isoformat(),
                        expires_at.isoformat(),
                        job_name,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO scheduler_locks (
                        job_name, lock_token, owner_id,
                        acquired_at, lock_expires_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        job_name,
                        token,
                        self.owner_id,
                        now.isoformat(),
                        expires_at.isoformat(),
                    ),
                )

            conn.commit()
            return token

        except sqlite3.Error as exc:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            logger.warning_ctx(
                "Acquisition de verrou impossible",
                context={"job_name": job_name, "erreur": str(exc)},
            )
            return None
        finally:
            conn.close()

    def release(self, job_name: str, token: str) -> None:
        conn = creer_connexion()
        try:
            conn.execute(
                """
                DELETE FROM scheduler_locks
                WHERE job_name = ?
                AND lock_token = ?
                """,
                (job_name, token),
            )
            conn.commit()
        finally:
            conn.close()

    def cleanup_expired_locks(self) -> int:
        """
        Supprime les locks expirés laissés par des processus crashés.
        Retourne le nombre de locks nettoyés.
        """
        conn = creer_connexion()
        try:
            now = datetime.now(timezone.utc)
            cursor = conn.execute(
                "DELETE FROM scheduler_locks WHERE lock_expires_at < ?",
                (now.isoformat(),),
            )
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info_ctx(
                    "Locks expirés nettoyés",
                    context={"count": count},
                )
            return count
        except sqlite3.Error as exc:
            logger.warning_ctx(
                "Erreur nettoyage locks expirés",
                context={"erreur": str(exc)},
            )
            return 0
        finally:
            conn.close()
