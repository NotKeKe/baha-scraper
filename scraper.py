from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import urljoin
import asyncio
from datetime import datetime, timezone
from markdownify import markdownify as md
from frozendict import frozendict
import orjson
import aiofiles
import logging

from utils import HttpxClient, SEM, DATA_DIR

logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self, title: str, bsn: str):
        self.title = title
        self.bsn = bsn

        self.running_tasks: list[asyncio.Task] = []

    async def _get_post_list(self) -> set[str]:
        async with SEM:
            resp = await HttpxClient.get(f'https://forum.gamer.com.tw/B.php?bsn={self.bsn}')
            if resp.status_code != 200: return set()
            logger.info(f'Got {self.bsn}\'s post list.')

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            all_a = soup.findAll('a')
            return set(urljoin(str(resp.url), a['href']) for a in all_a if a.get('href', '').startswith('C.php'))
        
    async def _get_post(self, post_url: str):
        async with SEM:
            try:
                resp = await HttpxClient.get(post_url)
                if resp.status_code != 200: return
                
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
                    if dislike_count == '-': # - 代表沒人點
                        dislike_count = 0
                    FINAL_RESULT['floors'][idx]['like_count'] = int(like_count)
                    FINAL_RESULT['floors'][idx]['dislike_count'] = int(dislike_count)
                    
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

                # 寫入
                async with aiofiles.open(DATA_DIR / f'{self.bsn}-{self.title}.jsonl', 'ab') as f:
                    await f.write(orjson.dumps(FINAL_RESULT) + b'\n')

                logger.info(f'Wrote {post_url}')
            except:
                logger.error(f'Error while fetching {post_url}', exc_info=True)

    
    async def scrape(self):
        try:
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
        except asyncio.CancelledError:
            pass