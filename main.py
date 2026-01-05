import asyncio
import os
import logging
import uvicorn

from src.main import main as scraper
from app.app import app

logger = logging.getLogger(__name__)

async def run_server():
    env_port = os.getenv("PORT")
    logger.info(f'Env PORT: `{env_port}`')
    if not env_port:
        logger.warning(f'Env PORT is not set, using default port 15913')
        env_port = 15913
    else:
        env_port = int(env_port)

    config = uvicorn.Config(app, host="0.0.0.0", port=env_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        scraper(),
        run_server(),
    )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info('Closing the main entry point...')
