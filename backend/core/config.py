"""
Configuration centrale du système.
Charge toutes les variables d'environnement
et les rend disponibles dans toute l'application.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import secrets


class Settings(BaseSettings):
    """
    Paramètres globaux du système.
    Chargés depuis les variables d'environnement.
    """

    # Environnement
    ENVIRONMENT: str = "development"

    # Sécurité
    SECRET_KEY: str = secrets.token_hex(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    ENCRYPTION_KEY: Optional[str] = None

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

    # Port
    PORT: int = 8000

    # Bankroll par défaut
    DEFAULT_INITIAL_BANKROLL: float = 150.0
    DEFAULT_KELLY_FRACTION: float = 0.125

    # Seuils du système
    MIN_CONFIDENCE_SIMPLE: float = 0.60
    MIN_CONFIDENCE_COMBINE: float = 0.65
    MIN_EV_THRESHOLD: float = 0.03
    MIN_PROB_EDGE: float = 0.05
    URGENCY_THRESHOLD: float = 0.85

    # Limites de paris
    MAX_SIMULTANEOUS_BETS: int = 3
    MIN_STAKE: float = 5.0
    MAX_STAKE_PCT: float = 0.10

    # Protection bankroll
    PROTECTION_THRESHOLD: float = 0.80
    SUSPENSION_THRESHOLD: float = 0.60

    # Dixon-Coles
    DC_XI: float = 0.0065
    DC_RHO: float = -0.13

    # Modèles
    MODELS_DIR: str = "./data/models"
    MAX_MODEL_VERSIONS: int = 3

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(
                f"ENVIRONMENT doit être parmi {allowed}"
            )
        return v

    @field_validator("FOOTYSTATS_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v and True:
            pass
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


settings = Settings()
