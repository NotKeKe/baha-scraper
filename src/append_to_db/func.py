import aiosqlite
from typing import Optional, Any

from .type import ThemeModel, PostModel
from .client import DB_PATH


# adds

async def add_to_all_themes(theme: ThemeModel | list[ThemeModel], db: Optional[aiosqlite.Connection] = None):
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            return await add_to_all_themes(theme, db=conn)

    if isinstance(theme, list):
        await db.executemany('''
        INSERT INTO all_themes (bsn, title, page_count)
        VALUES (?, ?, ?)
        ON CONFLICT (bsn) DO UPDATE SET 
            title = excluded.title,
            page_count = excluded.page_count,
            updated_at = CURRENT_TIMESTAMP
    ''', [(theme.bsn, theme.title, theme.page_count) for theme in theme])
    else:
        await db.execute('''
        INSERT INTO all_themes (bsn, title, page_count)
        VALUES (?, ?, ?)
        ON CONFLICT (bsn) DO UPDATE SET 
            title = excluded.title,
            page_count = excluded.page_count,
            updated_at = CURRENT_TIMESTAMP
    ''', (theme.bsn, theme.title, theme.page_count))
    await db.commit()

async def add_to_all_posts(post: PostModel | list[PostModel], db: Optional[aiosqlite.Connection] = None):
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            return await add_to_all_posts(post, db=conn)

    if isinstance(post, list):
        await db.executemany('''
        INSERT INTO all_posts (post_url, bsn)
        VALUES (?, ?)
        ON CONFLICT (post_url) DO UPDATE SET 
            bsn = excluded.bsn,
            updated_at = CURRENT_TIMESTAMP
    ''', [(post.post_url, post.bsn) for post in post])
    else:
        await db.execute('''
        INSERT INTO all_posts (post_url, bsn)
        VALUES (?, ?)
        ON CONFLICT (post_url) DO UPDATE SET 
            bsn = excluded.bsn,
            updated_at = CURRENT_TIMESTAMP
    ''', (post.post_url, post.bsn))
    await db.commit()

async def add_to_post_info(post_url: str, title: str, floors: str, db: Optional[aiosqlite.Connection] = None):
    """
    Args:
        post_url (str): _description_
        title (str): _description_
        floors (str): list 透過 orjson.dumps().decode() 轉換
        db (aiosqlite.Connection, optional): 資料庫連線
    """    
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            return await add_to_post_info(post_url, title, floors, db=conn)

    await db.execute('''
        INSERT INTO post_info (url, title, floors)
        VALUES (?, ?, ?)
        ON CONFLICT (url) DO UPDATE SET 
            title = excluded.title,
            floors = excluded.floors,
            updated_at = CURRENT_TIMESTAMP
    ''', (post_url, title, floors))
    await db.commit()


# finds
async def find_from_all_themes(query_key: str, query_value: Any, db: Optional[aiosqlite.Connection] = None) -> ThemeModel | None:
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            return await find_from_all_themes(query_key, query_value, db=conn)

    # 這樣才能 **
    db.row_factory = aiosqlite.Row

    cursor = await db.execute(f"SELECT * FROM all_themes WHERE {query_key} = ?", (query_value,))
    result = await cursor.fetchone()
    if result is None:
        return None
    return ThemeModel(**dict(result))


async def check_exists(table_name: str, key: str, value: Any, db: Optional[aiosqlite.Connection] = None) -> bool:
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            return await check_exists(table_name, key, value, db=conn)

    cursor = await db.execute(f"SELECT 1 FROM {table_name} WHERE {key} = ?", (value,))
    result = await cursor.fetchone()
    return result is not None

async def get_post_info(url: str, db: Optional[aiosqlite.Connection] = None) -> dict[str, Any] | None:
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            return await get_post_info(url, db=conn)

    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT * FROM post_info WHERE url = ?", (url,))
    result = await cursor.fetchone()
    if result:
        return dict(result)
    return None
