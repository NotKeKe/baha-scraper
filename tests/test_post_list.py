import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import urljoin
import time
import json

header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

page_count = 1

while True:
    url = f'https://api.gamer.com.tw/forum/v1/board_list.php?category=&page={page_count}&origin=forum'
    resp = requests.get(url, headers=header)
    if resp.status_code != 200:
        break
    data = resp.json()
    if not data['data']['list']: break


    time.sleep(1)
    page_count += 1

with open('test.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)