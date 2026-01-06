from pydantic import BaseModel

class ThemeModel(BaseModel):
    page_count: int
    bsn: str
    title: str