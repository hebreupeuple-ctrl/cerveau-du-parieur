"""
Système de logging centralisé.
Format JSON structuré pour Railway.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional
from backend.core.config import settings


class JSONFormatter(logging.Formatter):
    """
    Formateur JSON structuré.
    Chaque ligne de log est un objet JSON valide.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "environment": settings.ENVIRONMENT,
        }

        if hasattr(record, "context"):
            log_entry["context"] = record.context

        if hasattr(record, "task_name"):
            log_entry["task_name"] = record.task_name

        if hasattr(record, "attempt"):
            log_entry["attempt"] = record.attempt

        if record.exc_info:
            log_entry["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(log_entry, ensure_ascii=False)


class ContextLogger(logging.Logger):
    """
    Logger enrichi avec support du contexte structuré.
    """

    def info_ctx(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        extra = {"context": context or {}}
        extra.update(kwargs)
        self.info(message, extra=extra)

    def warning_ctx(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        extra = {"context": context or {}}
        extra.update(kwargs)
        self.warning(message, extra=extra)

    def error_ctx(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        extra = {"context": context or {}}
        extra.update(kwargs)
        self.error(message, extra=extra)

    def critical_ctx(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        extra = {"context": context or {}}
        extra.update(kwargs)
        self.critical(message, extra=extra)


def configurer_logging() -> None:
    """
    Configure le système de logging global.
    Appelé une seule fois au démarrage de l'application.
    """
    logging.setLoggerClass(ContextLogger)

    niveau = getattr(
        logging,
        settings.LOG_LEVEL.upper(),
        logging.INFO,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    logging.basicConfig(
        level=niveau,
        handlers=[handler],
        force=True,
    )

    # Réduire le bruit des bibliothèques externes
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING
    )
    logging.getLogger("uvicorn.error").setLevel(
        logging.WARNING
    )
    logging.getLogger("apscheduler").setLevel(
        logging.WARNING
    )
    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )
    logging.getLogger("aiohttp").setLevel(
        logging.WARNING
    )


def get_logger(name: str) -> ContextLogger:
    """
    Retourne un logger configuré pour un module.

    Usage dans chaque fichier :
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
