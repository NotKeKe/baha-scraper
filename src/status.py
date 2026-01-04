from typing import TypedDict
from datetime import datetime

class ScraperStatus(TypedDict):
    theme_title: str
    post_list_status: str
    post_status: str
    start_time: datetime
    end_time: datetime | None


class _Status:
    def __init__(self):
        self.curr_status = 'none'

        self.scrapers_status: dict[str, ScraperStatus] = {} # bsn: status

    @property
    def page_count(self):
        from .main import page_count
        return page_count

    @property
    def tasks(self):
        from .main import TASKS
        return TASKS

    @property
    def scrapers(self):
        from .utils import SCRAPERS
        return SCRAPERS

Status = _Status()