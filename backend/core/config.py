"""
Configuration centrale du système.
Charge toutes les variables d'environnement
et les rend disponibles dans toute l'application.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import Optional
import logging

_config_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Paramètres globaux du système.
    Chargés depuis les variables d'environnement.
    """

    # Environnement
    ENVIRONMENT: str = "development"

    # Sécurité — doit être définie dans .env en production
    SECRET_KEY: str = "dev-insecure-default-key-change-me-in-production-32x"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    ENCRYPTION_KEY: Optional[str] = None
    ADMIN_EMAILS: str = ""

    # FootyStats API
    FOOTYSTATS_API_KEY: str = ""
    FOOTYSTATS_BASE_URL: str = "https://api.football-data-api.com"

    # Base de données
    DATABASE_URL: str = "sqlite:///./data/cerveau.db"
    DATABASE_PATH: str = "./data/cerveau.db"

    # Notifications Push VAPID
    NOTIFICATION_VAPID_PUBLIC: Optional[str] = None
    NOTIFICATION_VAPID_PRIVATE: Optional[str] = None
    NOTIFICATION_VAPID_EMAIL: str = "mailto:vagharlegrand@gmail.com"

    # Limites API
    MAX_REQUESTS_PER_HOUR: int = 1600

    # Logs
    LOG_LEVEL: str = "INFO"

    # Backup
    BACKUP_DIR: str = "./data/backups"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Port
    PORT: int = 8000

    # Bankroll par défaut
    DEFAULT_INITIAL_BANKROLL: float = 150.0
    DEFAULT_KELLY_FRACTION: float = 0.125

    # Seuils du système
    MIN_CONFIDENCE_SIMPLE: float = 0.60
    MIN_CONFIDENCE_COMBINE: float = 0.65
    MIN_EV_THRESHOLD: float = 0.05   # Relevé de 3 % à 5 % pour plus de sélectivité
    MIN_PROB_EDGE: float = 0.05
    URGENCY_THRESHOLD: float = 0.85

    # Limites de paris
    MAX_SIMULTANEOUS_BETS: int = 3
    MIN_STAKE: float = 5.0
    MAX_STAKE_PCT: float = 0.10

    # Protection bankroll
    PROTECTION_THRESHOLD: float = 0.80
    SUSPENSION_THRESHOLD: float = 0.60

    # Dixon-Coles — demi-vie ≈ 49 jours (plus réactif)
    DC_XI: float = 0.014
    DC_RHO: float = -0.13

    # Modèles
    MODELS_DIR: str = "./data/models"
    MAX_MODEL_VERSIONS: int = 3

    # Automatisation
    SCHEDULER_ENABLED: bool = True
    AUTO_SYNC_ON_STARTUP: bool = True
    LEAGUE_SYNC_INTERVAL_HOURS: int = 24
    MARKET_REFRESH_INTERVAL_MINUTES: int = 60
    RESOLUTION_INTERVAL_MINUTES: int = 5
    HISTORICAL_FEATURE_BACKFILL_ENABLED: bool = True
    HISTORICAL_FEATURE_BACKFILL_INTERVAL_MINUTES: int = 60
    HISTORICAL_FEATURE_BACKFILL_BATCH_SIZE: int = 1000
    CATALOG_CHANGE_BACKFILL_MAX_BATCHES: int = 12
    MODEL_RETRAIN_INTERVAL_HOURS: int = 24
    MODEL_RETRAIN_INITIAL_DELAY_MINUTES: int = 10
    PLATT_RECAL_INTERVAL_HOURS: int = 48
    SYSTEM_JOB_LOCK_LEASE_MINUTES: int = 120

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(
                f"ENVIRONMENT doit être parmi {allowed}"
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v.startswith("dev-insecure-default"):
            _config_logger.warning(
                "SECRET_KEY utilise la valeur par défaut non sécurisée. "
                "Définissez SECRET_KEY dans votre fichier .env."
            )
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY.startswith("dev-insecure-default"):
                raise ValueError(
                    "SECRET_KEY doit être définie explicitement en production."
                )
        return self

    @field_validator("FOOTYSTATS_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            _config_logger.warning(
                "FOOTYSTATS_API_KEY non définie. "
                "La collecte de données ne fonctionnera pas."
            )
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def admin_emails(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.ADMIN_EMAILS.split(",")
            if email.strip()
        }


settings = Settings()
