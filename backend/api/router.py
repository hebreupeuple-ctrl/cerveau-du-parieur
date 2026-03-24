"""
Routeur principal FastAPI.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from backend.core.logging import configurer_logging, get_logger
from backend.core.config import settings

configurer_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Demarrage du Cerveau du Parieur")

    from backend.database.connection import obtenir_connexion
    from backend.database.migrations import appliquer_migrations
    from backend.scheduler.runtime import AutomationScheduler

    conn = obtenir_connexion()
    appliquer_migrations(conn)
    logger.info("Base de donnees initialisee")

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.api.endpoints import auth, pronostics, performance, systeme

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(pronostics.router, prefix="/api/v1/pronostics", tags=["pronostics"])
    app.include_router(performance.router, prefix="/api/v1/performance", tags=["performance"])
    app.include_router(systeme.router, prefix="/api/v1/system", tags=["system"])

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
        logger.error_ctx(
            "Erreur non geree",
            context={"erreur": str(exc)},
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
