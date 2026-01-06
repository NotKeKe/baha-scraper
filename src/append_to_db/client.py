import aiosqlite
from pathlib import Path

DB_PATH = "data/db/data.db"
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

DB_CLIENT: aiosqlite.Connection | None = None

async def get_client():
    global DB_CLIENT
    if DB_CLIENT is None:
        DB_CLIENT = await aiosqlite.connect(DB_PATH)
    return DB_CLIENT

async def close_client():
    global DB_CLIENT
    if DB_CLIENT:
        await DB_CLIENT.close()
        DB_CLIENT = None

async def init_tables():
    db = await get_client()


    await db.execute("PRAGMA journal_mode = WAL") # 讀寫並行


    '''
    用來儲存
    f'https://api.gamer.com.tw/forum/v1/board_list.php?category=&page={page_count}&origin=forum'
    的後 100 rank(不含) 的資料
    '''
    # 主題排名
    await db.execute("""
        CREATE TABLE IF NOT EXISTS all_themes (
            bsn TEXT PRIMARY KEY,
            title TEXT,
            page_count INTEGER,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    

    '''
    '''
    # 單一主題的 全部貼文連結
    await db.execute("""
        CREATE TABLE IF NOT EXISTS all_posts (
            post_url TEXT PRIMARY KEY,
            bsn TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 建立索引
    await db.execute("CREATE INDEX IF NOT EXISTS idx_posts_bsn ON all_posts (bsn)")

    '''
    url 為主鍵
    floors 為 JSON 格式
    '''
    # 單一貼文的資訊
    await db.execute("""
        CREATE TABLE IF NOT EXISTS post_info (
            url TEXT PRIMARY KEY,
            title TEXT,
            floors TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.commit()