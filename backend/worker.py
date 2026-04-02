"""
Point d'entree worker Railway.
Lance uniquement le scheduler applicatif sans serveur HTTP.
"""

import asyncio
import signal

from backend.core.logging import configurer_logging, get_logger
from backend.database.connection import fermer_connexion, obtenir_connexion
from backend.scheduler.runtime import AutomationScheduler

configurer_logging()
logger = get_logger(__name__)


async def run_worker() -> None:
    logger.info("Demarrage du worker scheduler")

    obtenir_connexion()
    scheduler = AutomationScheduler()
    await scheduler.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Fallback pour les plateformes sans support add_signal_handler.
            signal.signal(sig, lambda *_args: stop_event.set())

    try:
        await stop_event.wait()
    finally:
        await scheduler.stop()
        fermer_connexion()
        logger.info("Arret du worker scheduler")


if __name__ == "__main__":
    asyncio.run(run_worker())
