import asyncio

from src.scraper import Scraper

async def main():
    scraper = Scraper('test', '1')
    await scraper.scrape()

asyncio.run(main())
