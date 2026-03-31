"""
Routeur principal FastAPI.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
from contextlib import asynccontextmanager
from backend.core.logging import configurer_logging, get_logger
from backend.core.config import settings
from backend.api.middleware.rate_limiter import RateLimiterMiddleware

configurer_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Demarrage du Cerveau du Parieur")

    from backend.database.connection import obtenir_connexion
    from backend.database.migrations import appliquer_migrations
    from backend.scheduler.runtime import AutomationScheduler

    db_path = settings.DATABASE_PATH
    db_exists = os.path.exists(db_path)
    db_size = os.path.getsize(db_path) if db_exists else 0
    logger.info_ctx(
        "Volume persistant — vérification base de données",
        context={
            "path": db_path,
            "exists": db_exists,
            "size_bytes": db_size,
        },
    )

    conn = obtenir_connexion()
    appliquer_migrations(conn)
    logger.info("Base de donnees initialisee")

    # Réentraîner si le modèle stocké est obsolète (mauvais nombre de features)
    # Lancé en tâche de fond pour ne pas bloquer le démarrage du serveur
    from backend.models.trainer import ModelTrainer
    trainer = ModelTrainer(conn)
    trainer._charger_modeles()
    if not trainer.modeles:
        logger.info("Modele absent — réentraînement en arrière-plan")
        async def _retrain_bg():
            try:
                from backend.scheduler.tasks.automation import entrainer_modele
                await entrainer_modele()
                logger.info("Réentraînement au démarrage terminé")
            except Exception as exc:
                logger.error_ctx(
                    "Echec réentraînement au démarrage",
                    context={"erreur": str(exc)},
                )
        asyncio.create_task(_retrain_bg())

    scheduler = AutomationScheduler()
    app.state.scheduler = scheduler
    await scheduler.start()

    yield

    await scheduler.stop()

    from backend.database.connection import fermer_connexion
    fermer_connexion()
    logger.info("Arret du serveur")


def creer_app(env: str = None) -> FastAPI:
    app = FastAPI(
        title="Cerveau du Parieur",
        version="1.0.0",
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    allowed_origins = [
        o.strip()
        for o in settings.ALLOWED_ORIGINS.split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimiterMiddleware)

    from backend.api.endpoints import auth, pronostics, performance, systeme, analyse

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(pronostics.router, prefix="/api/v1/pronostics", tags=["pronostics"])
    app.include_router(performance.router, prefix="/api/v1/performance", tags=["performance"])
    app.include_router(systeme.router, prefix="/api/v1/system", tags=["system"])
    app.include_router(analyse.router, prefix="/api/v1/analyse", tags=["analyse"])

    from fastapi import HTTPException as FastAPIHTTPException

    @app.exception_handler(FastAPIHTTPException)
    async def http_exception_handler(request, exc):
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", f"HTTP_{exc.status_code}")
            message = exc.detail.get("message", str(exc.detail))
        else:
            code = f"HTTP_{exc.status_code}"
            message = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": code, "message": message},
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        from backend.core.exceptions import CerveauException
        if isinstance(exc, CerveauException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                    }
                }
            )
        import traceback
        logger.error_ctx(
            "Erreur non geree",
            context={
                "erreur": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "SYSTEM_ERROR",
                    "message": "Erreur interne du serveur",
                }
            }
        )

    return app


app = creer_app()
