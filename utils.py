from __future__ import annotations

import httpx
import asyncio
from typing import TYPE_CHECKING
from pathlib import Path
import logging
import logging.handlers
import sys

if TYPE_CHECKING:
    from scraper import Scraper


_limit = httpx.Limits(max_keepalive_connections=51, max_connections=50)
header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

HttpxClient = httpx.AsyncClient(limits=_limit, headers=header) # cookie 會被自動維護

SCRAPERS: list[Scraper] = []

SEM = asyncio.Semaphore(30)

DATA_DIR = Path(__file__).parent / 'data'
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
    console_handler = logging.StreamHandler()
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