import aiosqlite
from typing import Any

from .type import ThemeModel, PostModel
from .client import get_client


# adds

async def add_to_all_themes(theme: ThemeModel | list[ThemeModel]):
    db = await get_client()

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

async def add_to_all_posts(post: PostModel | list[PostModel]):
    db = await get_client()

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

async def add_to_post_info(post_url: str, title: str, floors: str):
    """
    Args:
        post_url (str): _description_
        title (str): _description_
        floors (str): list 透過 orjson.dumps().decode() 轉換
    """    
    db = await get_client()

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
async def find_from_all_themes(query_key: str, query_value: Any) -> ThemeModel | None:
    db = await get_client()

    # 這樣才能 **
    db.row_factory = aiosqlite.Row

    cursor = await db.execute(f"SELECT * FROM all_themes WHERE {query_key} = ?", (query_value,))
    result = await cursor.fetchone()
    if result is None:
        return None
    return ThemeModel(**dict(result))


async def check_exists(table_name: str, key: str, value: Any) -> bool:
    db = await get_client()

    cursor = await db.execute(f"SELECT 1 FROM {table_name} WHERE {key} = ?", (value,))
    result = await cursor.fetchone()
    return result is not None

async def get_post_info(url: str) -> dict[str, Any] | None:
    db = await get_client()

    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT * FROM post_info WHERE url = ?", (url,))
    result = await cursor.fetchone()
    if result:
        return dict(result)
    return None
