import asyncio
import logging

from .utils import HttpxClient, SCRAPERS, update_status, init_httpx_client, close_httpx_client
from .scraper import Scraper

logger = logging.getLogger(__name__)
page_count = 0
TASKS = []

async def main():
    global page_count, TASKS
    try:
        # init httpx client
        await init_httpx_client()
        assert HttpxClient is not None

        page_count = 1
        logger.info('Fetching all themes...')
        update_status('fetching_all_themes_start')
        while True:
            url = f'https://api.gamer.com.tw/forum/v1/board_list.php?category=&page={page_count}&origin=forum'
            # Retry logic for 429
            for _ in range(5):
                resp = await HttpxClient.get(url)
                if resp.status_code == 429:
                    logger.warning(f"Got 429 for {url}, waiting 5s...")
                    await asyncio.sleep(5)
                    continue
                break

            if resp.status_code != 200:
                logger.error(f"Failed to fetch board list: {resp.status_code}")
                break

            data = resp.json()
            all_list = data['data']['list']
            if not all_list: break

            # get info
            all_themes = [
                (item['title'].strip(), item["bsn"]) # 主題, 該主題的 bsn
                for item in all_list
            ]

            # 遍歷所有主題
            for title, bsn in all_themes:
                scraper = Scraper(title, bsn)
                SCRAPERS.append(scraper)
                await asyncio.sleep(0.00001)
                

            page_count += 1
            update_status(f'fetching_all_themes_{page_count}')

        update_status('fetching_all_themes_end')
        TASKS = [asyncio.create_task(scraper.scrape()) for scraper in SCRAPERS]
        logger.info('Scraping all themes...')
        update_status('scraping_all_themes_start')
        await asyncio.gather(*TASKS)
        update_status('scraping_all_themes_end')

    except (asyncio.CancelledError, KeyboardInterrupt): 
        pass

    finally:
        logger.info('Closing...')

        # close scraper
        for scraper in SCRAPERS:
            await scraper.close()

        # close tasks for scraper
        for task in TASKS:
            task.cancel()

        try:
            await asyncio.gather(*TASKS)
        except asyncio.CancelledError:
            pass
        except:
            logger.error('Error while closing TASKS', exc_info=True)

        # close httpx client
        await close_httpx_client()


if __name__ == '__main__':
    asyncio.run(main())
