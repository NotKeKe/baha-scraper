import asyncio
import logging

from . import utils
from .utils import HttpxClient, SCRAPERS, update_status, init_httpx_client, close_httpx_client
from .scraper import Scraper
from .append_to_db import (
    init_tables,
    get_client as get_db_client,
    close_client as close_db_client,
    add_to_all_themes,
)
from .append_to_db.type import ThemeModel

logger = logging.getLogger(__name__)
page_count = 0
TASKS = []

async def main():
    global page_count, TASKS
    try:
        # init httpx client
        await init_httpx_client()
        assert HttpxClient is not None

        # init tables
        await init_tables()

        page_count = 1
        logger.info('Fetching all themes...')
        update_status('fetching_all_themes_start')

        conn = await get_db_client()
        while True:
            # 1. 嘗試從資料庫讀取這頁的「新鮮」快取 (7天內)
            cursor = await conn.execute("""
                SELECT title, bsn FROM all_themes 
                WHERE page_count = ? 
                AND updated_at >= datetime('now', '-7 days')
            """, (page_count,))
            cached_rows = await cursor.fetchall()
            
            current_page_themes = []

            if cached_rows:
                logger.info(f"Using cached themes for page {page_count}")
                # 轉換回 (title, bsn) 格式
                current_page_themes = [(row[0], row[1]) for row in cached_rows]
            else:
                # 2. 如果沒有快取或已過期，則抓取 API
                url = f'https://api.gamer.com.tw/forum/v1/board_list.php?category=&page={page_count}&origin=forum'
                
                # Retry logic for 429
                resp = None
                for _ in range(5):
                    resp = await HttpxClient.get(url)
                    if resp.status_code == 429:
                        if resp.headers.get('Retry-After'):
                            wait_time = int(resp.headers.get('Retry-After'))
                        else:
                            wait_time = 5

                        logger.warning(f"Got 429 for {url}, waiting {wait_time}s(isRetryAfter: {resp.headers.get('Retry-After') is not None})...")
                        await asyncio.sleep(wait_time)
                        continue
                    break

                if not resp or resp.status_code != 200:
                    logger.error(f"Failed to fetch board list: {resp.status_code if resp else 'No response'}")
                    break

                data = resp.json()
                all_list = data['data']['list']
                if not all_list: 
                    break # 資料抓完了，跳出 while

                current_page_themes = [
                    (item['title'].strip(), str(item["bsn"])) 
                    for item in all_list
                ]

                # update to db
                utils.WRITE_DB_TASKS.append(asyncio.create_task(add_to_all_themes([
                    ThemeModel(title=title, bsn=bsn, page_count=page_count)
                    for title, bsn in current_page_themes
                ])))

            # create scraper
            for title, bsn in current_page_themes:
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
    except:
        logger.error('Error while scraping', exc_info=True)
    finally:
        logger.info('Closing...')

        # close scraper
        for scraper in SCRAPERS:
            await scraper.close()

        # close db write tasks
        for task in utils.WRITE_DB_TASKS:
            task.cancel()

        try:
            await asyncio.gather(*utils.WRITE_DB_TASKS)
        except asyncio.CancelledError:
            pass
        except:
            logger.error('Error while closing WRITE_DB_TASKS', exc_info=True)

        # close tasks for scraper
        for task in TASKS:
            task.cancel()

        try:
            await asyncio.gather(*TASKS)
        except asyncio.CancelledError:
            pass
        except:
            logger.error('Error while closing TASKS', exc_info=True)

        # close db client
        await close_db_client()

        # close httpx client
        await close_httpx_client()


if __name__ == '__main__':
    asyncio.run(main())
