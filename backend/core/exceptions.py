"""
Exceptions personnalisées du système.
Chaque exception correspond à un code d'erreur
défini dans le contrat API.
"""


class CerveauException(Exception):
    """Exception de base du système."""

    def __init__(
        self,
        message: str,
        code: str = "SYSTEM_ERROR",
        status_code: int = 500,
        details: dict = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# Authentification
class AuthException(CerveauException):
    def __init__(self, message: str, code: str):
        super().__init__(
            message=message,
            code=code,
            status_code=401,
        )


class InvalidCredentialsException(AuthException):
    def __init__(self):
        super().__init__(
            message="Email ou mot de passe incorrect",
            code="AUTH_INVALID_CREDENTIALS",
        )


class TokenExpiredException(AuthException):
    def __init__(self):
        super().__init__(
            message="Token expiré",
            code="AUTH_TOKEN_EXPIRED",
        )


class TokenInvalidException(AuthException):
    def __init__(self):
        super().__init__(
            message="Token invalide",
            code="AUTH_TOKEN_INVALID",
        )


class DeviceNotAuthorizedException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Appareil non autorisé",
            code="AUTH_DEVICE_NOT_AUTHORIZED",
            status_code=403,
        )


class AccountLockedException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Compte temporairement verrouillé",
            code="AUTH_ACCOUNT_LOCKED",
            status_code=403,
        )


class TooManyAttemptsException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Trop de tentatives de connexion",
            code="AUTH_TOO_MANY_ATTEMPTS",
            status_code=429,
        )


# Ressources
class ResourceNotFoundException(CerveauException):
    def __init__(self, resource: str):
        super().__init__(
            message=f"{resource} introuvable",
            code="RESOURCE_NOT_FOUND",
            status_code=404,
        )


class ResourceAlreadyExistsException(CerveauException):
    def __init__(self, resource: str):
        super().__init__(
            message=f"{resource} existe déjà",
            code="RESOURCE_ALREADY_EXISTS",
            status_code=409,
        )


# Validation
class ValidationException(CerveauException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


# Pronostics
class PronosticAlreadyPlacedException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Ce pari a déjà été placé",
            code="PRONOSTIC_ALREADY_PLACED",
            status_code=409,
        )


class PronosticMatchStartedException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Le match a déjà commencé",
            code="PRONOSTIC_MATCH_STARTED",
            status_code=409,
        )


class PronosticExpiredException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Ce pronostic a expiré",
            code="PRONOSTIC_EXPIRED",
            status_code=409,
        )


# Bankroll
class BankrollInsufficientException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Bankroll insuffisante pour cette mise",
            code="BANKROLL_INSUFFICIENT",
            status_code=400,
        )


# Système
class RateLimitExceededException(CerveauException):
    def __init__(self):
        super().__init__(
            message="Limite de requêtes dépassée",
            code="SYSTEM_RATE_LIMIT_EXCEEDED",
            status_code=429,
        )


class FootyStatsUnavailableException(CerveauException):
    def __init__(self):
        super().__init__(
            message="FootyStats API indisponible",
            code="FOOTYSTATS_UNAVAILABLE",
            status_code=503,
        )
