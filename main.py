import asyncio

from src.main import main as scraper
from app.app import app

import uvicorn

async def run_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=80, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(
        scraper(),
        run_server(),
    )


if __name__ == '__main__':
    asyncio.run(main())
