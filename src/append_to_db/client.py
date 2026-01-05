import aiosqlite

async def init_tables():
    async with aiosqlite.connect("data/db.db") as db:
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