# 一托答辯的代碼

from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import urljoin
import asyncio
from datetime import datetime, timezone
from httpx import Response
from markdownify import markdownify as md
from frozendict import frozendict
import orjson
import aiofiles
import logging
from typing import Any
import random

from .append_to_db import get_post_info, add_to_post_info, add_to_all_posts, get_client as get_db_client
from .append_to_db.type import PostModel
from . import utils
from .utils import HttpxClient, SEM, DATA_DIR, init_httpx_client, safe_filename
from .status import Status

logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self, title: str, bsn: str):
        self.title = title # theme title
        self.bsn = bsn

        self.running_tasks: list[asyncio.Task] = []
        Status.scrapers_status[self.bsn] = {
            'theme_title': self.title,
            'post_list_status': 'none',
            'post_status': 'none',
            'start_time': datetime.now(timezone.utc),
            'end_time': None
        }   

        self.is_first_run: bool = True

        self.WRITE_LOCK = asyncio.Lock()

    def _update_status(self, key: str, value: Any):
        if key not in Status.scrapers_status[self.bsn]:
            raise ValueError(f'Invalid key: {key}')
        Status.scrapers_status[self.bsn][key] = value
    
    async def _fetch_with_retry(self, url: str, retries: int = 5) -> Response | None:
        base_delay = 5
        assert HttpxClient is not None
        for i in range(retries):
            try:
                resp = await HttpxClient.get(url)
                if resp.status_code == 429:
                    if not resp.headers.get('Retry-After'):
                        wait_time = base_delay * (2 ** i) + random.uniform(0, 3)
                    else:
                        wait_time = int(resp.headers.get('Retry-After'))
                        
                    logger.warning(f"Got 429 for {url}, waiting {wait_time:.2f}s(isRetryAfter: {resp.headers.get('Retry-After') is not None})...")
                    self._update_status('post_status', f'waiting_429_{int(wait_time)}s')
                    await asyncio.sleep(wait_time)
                    continue
                return resp
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                await asyncio.sleep(random.uniform(1, 3))
        return None

    async def _get_post_list(self) -> set[str]: # B.php, 單一bsn 的全部貼文連結
        async with SEM:
            await init_httpx_client()
            assert HttpxClient is not None

            self._update_status('post_list_status', 'fetching')

            # 快取檢查
            db = await get_db_client()
            cursor = await db.execute("""
                SELECT post_url FROM all_posts 
                WHERE bsn = ? 
                AND updated_at >= datetime('now', '-1 hour')
            """, (self.bsn,))
            cached_rows = await cursor.fetchall()
                
            if cached_rows:
                cached_list = list(cached_rows)
                logger.info(f"Cache hit for post list: {self.bsn} ({len(cached_list)} posts)")
                self._update_status('post_list_status', 'fetched')
                return set(row[0] for row in cached_list)

            # 沒有快取，執行爬取
            page_count = 1
            all_urls = set()

            while True:
                resp = await self._fetch_with_retry(f'https://forum.gamer.com.tw/B.php?page={page_count}&bsn={self.bsn}')
                if not resp or resp.status_code != 200: 
                    logger.info(f'Failed to get {self.bsn}\'s post list, status code: {resp.status_code if resp else "None"}')
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                
                all_a = soup.findAll('a')
                _all_urls = set(urljoin(str(resp.url), a['href']) for a in all_a if a.get('href', '').startswith('C.php'))
                all_urls.update(_all_urls)
                
                page_count += 1
                await asyncio.sleep(random.uniform(1, 3))

            # 存入快取
            utils.WRITE_DB_TASKS.append(asyncio.create_task(
                add_to_all_posts([PostModel(bsn=self.bsn, post_url=url) for url in all_urls])
            ))

            self._update_status('post_list_status', 'fetched')
            return all_urls


    async def _get_post(self, post_url: str): # C.php, 單一貼文
        # 這長度大概算是一種屎山代碼了哈哈
        async with SEM:
            await init_httpx_client()
            assert HttpxClient is not None

            try:
                self._update_status('post_status', f'fetching_{post_url}')

                # 快取
                cached_data = await get_post_info(post_url)
                
                if cached_data:
                    floors = orjson.loads(cached_data['floors'])
                    if floors and len(floors) > 0:
                        iso_time = floors[0].get('time')
                        if iso_time:
                            post_time = datetime.fromisoformat(iso_time)
                            # 如果樓主貼文超過 30 天，直接使用快取
                            # 因為我希望他有機會的話，去更新留言。一篇貼聞過 30 天大概也不會火了 (吧
                            if (datetime.now(timezone.utc) - post_time).days > 30:
                                CACHED_RESULT = {
                                    'title': cached_data['title'],
                                    'url': post_url,
                                    'floors': floors
                                }
                                # 寫入檔案
                                async with self.WRITE_LOCK:
                                    # 第一次跑就清空檔案
                                    if self.is_first_run:
                                        self.is_first_run = False
                                        async with aiofiles.open(DATA_DIR / f'{self.bsn}-{safe_filename(self.title)}.jsonl', 'wb') as f:
                                            await f.write(b'')
                                    async with aiofiles.open(DATA_DIR / f'{self.bsn}-{safe_filename(self.title)}.jsonl', 'ab') as f:
                                        await f.write(orjson.dumps(CACHED_RESULT) + b'\n')

                                logger.info(f'Wrote {post_url} (Cache hit)')
                                self._update_status('post_status', f'fetched_{post_url}')
                                return



                resp = await self._fetch_with_retry(post_url)
                if not resp or resp.status_code != 200: 
                    logger.info(f'Failed to get {post_url}, status code: {resp.status_code if resp else "None"}')
                    return
                    
                soup = BeautifulSoup(resp.text, 'html.parser')

                # 該篇貼文的 標題
                title = soup.select('.c-post__header__title')[0].text.strip()
                FINAL_RESULT = {
                    'theme_title': self.title,
                    'title': title,
                    'url': post_url,
                    'floors': []
                }

                for idx, post in enumerate(soup.select('.c-post')):
                    assert isinstance(post, Tag)
                    FINAL_RESULT['floors'].append({'index': idx})

                    # get tag，基本上一篇文章只有一個 tag
                    FINAL_RESULT['floors'][idx]['tags'] = {}
                    tags = post.select('.tag-category a')
                    for tag in tags:
                        tag_href = tag.get('href')
                        tag_text = tag.find('div').get_text(strip=True)
                        FINAL_RESULT['floors'][idx]['tags'][tag_text] = tag_href

                    # 取得 author 資訊
                    div_author = post.select('.c-post__header__author')[0]
                    author_name = div_author.select('.username')[0].text.strip()
                    author_id = div_author.select('.userid')[0].text.strip()
                    author_url = urljoin(post_url, div_author.select('.userid')[0].get('href'))
                    FINAL_RESULT['floors'][idx]['author'] = {
                        'name': author_name,
                        'id': author_id,
                        'url': author_url
                    }
                    
                    # 取得時間資訊
                    div_info = post.select('.c-post__header__info')[0]
                    time_str = div_info.select('.edittime')[0].get('data-mtime')
                    utc8_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    utc_time = utc8_time.astimezone(timezone.utc)
                    utc_time_iso = utc_time.isoformat()
                    FINAL_RESULT['floors'][idx]['time'] = utc_time_iso    
                    
                    # 取得內文
                    article = post.select('article div')[0]
                    article_text = md(str(article))
                    FINAL_RESULT['floors'][idx]['content'] = article_text

                    # 取得點讚
                    div_button_bar = post.select('.c-post__body__buttonbar')[0]
                    assert isinstance(div_button_bar, Tag)
                    like_count = div_button_bar.select('.gp a')[0].text.strip()
                    dislike_count = div_button_bar.select('.bp a')[0].text.strip()
                    
                    if like_count == '-': # - 代表沒人點
                        like_count = 0
                    if dislike_count == '-': # - 代表沒人點
                        dislike_count = 0
                        
                    try:
                        FINAL_RESULT['floors'][idx]['like_count'] = int(like_count)
                    except:
                        FINAL_RESULT['floors'][idx]['like_count'] = 1000 # 有可能出現為爆
                    try:
                        FINAL_RESULT['floors'][idx]['dislike_count'] = int(dislike_count)
                    except:
                        FINAL_RESULT['floors'][idx]['dislike_count'] = 1000 # 有可能出現為爆
                    
                    # 取得留言
                    comments = set()

                    div_comment = post.select('.c-reply')[0]
                    assert isinstance(div_comment, Tag)
                    for div in div_comment.select('div'): # 每個留言
                        assert isinstance(div, Tag)
                        div_reply_item = div.select('div')
                        if not div_reply_item:
                            continue
                        div_reply_item = div_reply_item[0]
                        assert isinstance(div_reply_item, Tag)

                        # Start 找頭貼
                        a_reply_avatar = div_reply_item.select('.reply-avatar')
                        if not a_reply_avatar:
                            continue
                        a_reply_avatar = a_reply_avatar[0]
                        assert isinstance(a_reply_avatar, Tag)

                        # End 找頭貼
                        avatar_url = a_reply_avatar.select('img')[0].get('data-src').strip()

                        # Start 找使用者
                        div_reply_content = div_reply_item.select('.reply-content')[0]
                        user_href = div_reply_content.select('a')[0].get('href').strip()

                        # End 找使用者
                        user_url = urljoin(post_url, user_href)
                        user_name = div_reply_content.select('a')[0].text.strip()
                        comment_text = div_reply_content.select('article span')[0].text.strip()

                        # Start 找時間
                        div_all_edit_time = div_reply_item.find_all('div', class_='edittime')

                        # End 找時間
                        utc8_time = ' '.join(div_all_edit_time[1].get('data-tippy-content').split()[1:])
                        utc_time = datetime.strptime(utc8_time, '%Y-%m-%d %H:%M:%S')
                        utc_time = utc_time.astimezone(timezone.utc)
                        utc_time_iso = utc_time.isoformat()

                        floor = div_all_edit_time[0].text.strip()

                        comments.add(frozendict({ # 我不知道為什麼會有重複的
                            'avatar_url': avatar_url,
                            'user_url': user_url,
                            'user_name': user_name,
                            'comment_text': comment_text,
                            'floor': floor,
                            'time': utc_time_iso
                        }))

                    comments = list(comments)
                    comments.sort(key=lambda x: int(x['floor'][1:])) # B1 -> 1
                    FINAL_RESULT['floors'][idx]['comments'] = comments

                # 同步到資料庫
                await add_to_post_info(post_url, title, orjson.dumps(FINAL_RESULT['floors']).decode())

                # 寫入檔案
                async with self.WRITE_LOCK:
                    if self.is_first_run:
                        # 第一次啟動的話就清空原本的檔案，因為可能會手動進行多次爬蟲
                        self.is_first_run = False
                        async with aiofiles.open(DATA_DIR / f'{self.bsn}-{safe_filename(self.title)}.jsonl', 'wb') as f:
                            await f.write(b'')

                    async with aiofiles.open(DATA_DIR / f'{self.bsn}-{safe_filename(self.title)}.jsonl', 'ab') as f:
                        await f.write(orjson.dumps(FINAL_RESULT) + b'\n')

                logger.info(f'Wrote {post_url}')
                self._update_status('post_status', f'fetched_{post_url}')
            except:
                logger.error(f'Error while fetching {post_url}', exc_info=True)
            finally:
                await asyncio.sleep(random.uniform(1, 3)) # 休息 1-3 秒

    
    async def scrape(self):
        try:
            await init_httpx_client()
            post_list = await self._get_post_list()

            for post_url in post_list:
                self.running_tasks.append(asyncio.create_task(self._get_post(post_url)))

            await asyncio.gather(*self.running_tasks)
        finally:
            await self.close()

    async def close(self):
        try:
            for task in self.running_tasks:
                task.cancel()

            await asyncio.gather(*self.running_tasks)
            self._update_status('end_time', datetime.now(timezone.utc))
        except asyncio.CancelledError:
            pass