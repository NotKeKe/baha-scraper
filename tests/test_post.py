import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import urljoin
from datetime import datetime, timezone
from markdownify import markdownify as md
import json
from frozendict import frozendict

header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

url = 'https://forum.gamer.com.tw/C.php?bsn=17608&snA=28143&tnum=1&subbsn=15'
resp = requests.get(url, headers=header)

soup = BeautifulSoup(resp.text, 'html.parser')

FINAL_RESULT = {}

# 該篇貼文的 標題
title = soup.select('.c-post__header__title')[0].text.strip()
FINAL_RESULT['title'] = title
FINAL_RESULT['url'] = url
FINAL_RESULT['floors'] = []

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
    author_url = urljoin(resp.url, div_author.select('.userid')[0].get('href'))
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
        user_url = urljoin(resp.url, user_href)
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


with open('test.json', 'w', encoding='utf-8') as f:
    json.dump(FINAL_RESULT, f, ensure_ascii=False, indent=4)
