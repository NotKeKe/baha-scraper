from __future__ import annotations

import httpx
import asyncio
from typing import TYPE_CHECKING
from pathlib import Path
import logging
import logging.handlers
import sys
import os
import re

if TYPE_CHECKING:
    from scraper import Scraper

TOP_SCRAPE_TASK: asyncio.Task | None = None

_limit = httpx.Limits(max_keepalive_connections=51, max_connections=50)
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

HttpxClient: httpx.AsyncClient | None = httpx.AsyncClient(limits=_limit, headers=headers, proxy=os.getenv("HTTP_PROXY"))

async def init_httpx_client():
    global HttpxClient
    if HttpxClient is None or HttpxClient.is_closed:
        HttpxClient = httpx.AsyncClient(
            limits=_limit, 
            headers=headers, 
            proxy=os.getenv("HTTP_PROXY")
        )

async def close_httpx_client():
    global HttpxClient
    if HttpxClient and not HttpxClient.is_closed:
        await HttpxClient.aclose()
    HttpxClient = None

SCRAPERS: list[Scraper] = []
WRITE_DB_TASKS: list[asyncio.Task] = []

SEM = asyncio.Semaphore(5)

DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

def setup_logging():
    # 格式器 (Formatter) 維持不變，寫得很好
    log_format = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 根記錄器 (Root logger) 的設定維持不變
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # 終端機 Handler 維持不變
    console_handler = logging.StreamHandler(sys.__stderr__)
    console_handler.setFormatter(log_format)
  
    # --- 主要修改的部分在這裡 ---
    # 將 RotatingFileHandler 換成 TimedRotatingFileHandler
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "bot.log",  # 主要日誌檔的名稱
        when='D',                     # 'D' 代表按天 (Day) 輪替
        interval=1,                   # 間隔為 1 天
        backupCount=10,               # 保留 10 個舊的日誌檔案 (等於保留10天的紀錄)
        encoding="utf-8",
    )
    # --------------------------

    file_handler.setFormatter(log_format)

    # 避免重複加入 Handler 的邏輯維持不變，這是一個好習慣
    if root_logger.handlers: # 如果已經有 handler 了
        for handler in root_logger.handlers[:]: # 遍歷一個副本，以便安全移除
            root_logger.removeHandler(handler)
            
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        # 避免記錄空行
        if message.rstrip() != "":
            self.logger.log(self.level, message.rstrip())

    def flush(self):
        # logging 的 handlers 會自動處理 flush，所以這裡可以 pass
        pass

    def isatty(self):
        return False

sys.stdout = StreamToLogger(logging.getLogger("stdout"), logging.INFO)
sys.stderr = StreamToLogger(logging.getLogger("stderr"), logging.ERROR)
setup_logging()

def update_status(status_str: str):
    from .status import Status
    Status.curr_status = status_str

unname_file_idx = 1
def safe_filename(filename: str, replacement="_") -> str:
    global unname_file_idx
    # 1. 替換掉 Windows 禁用的字元: < > : " / \ | ? * 以及控制字元 (0-31)
    # [<>:"/\\|?*\x00-\x1f]
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', replacement, filename)
    
    # 2. 移除結尾的空格與句點 (Windows 會自動修剪掉，但為了安全建議手動處理)
    filename = filename.rstrip(". ")
    
    # 3. 處理 Windows 保留名稱 (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    # 如果檔名剛好是這些，就在前面加個底線或其他字元
    reserved_names = r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$"
    if re.match(reserved_names, filename, re.IGNORECASE):
        filename = replacement + filename
        
    # 4. 確保檔名不為空且長度限制 (Windows 一般限制為 255 字元)
    if not filename:
        filename = "unnamed_file" + str(unname_file_idx)
        unname_file_idx += 1
        
    return filename[:255]