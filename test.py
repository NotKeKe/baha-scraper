import asyncio

from scraper import Scraper

async def main():
    scraper = Scraper('test', '17608')
    print(await scraper._get_post_list())

asyncio.run(main())
