from pydantic import BaseModel
from typing import Any

class ThemeModel(BaseModel):
    page_count: int
    bsn: str
    title: str

class PostModel(BaseModel):
    bsn: str
    post_url: str

class PostInfoModel(BaseModel): ...