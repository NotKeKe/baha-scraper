from fastapi import FastAPI
import psutil
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from src.status import Status

app = FastAPI()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get('/')
async def read_root():
    return FileResponse(os.path.join(static_dir, 'index.html'))

@app.get('/api/status')
async def get_status(page: int = 1, limit: int = 20, q: str = ''):
    # Filter scrapers
    filtered_scrapers = {}
    q = q.lower().strip()
    
    for bsn, status in Status.scrapers_status.items():
        if not q or q in str(bsn).lower() or q in status.get('theme_title', '').lower():
            filtered_scrapers[bsn] = status

    # Pagination
    scrapers_list = list(filtered_scrapers.items())
    # Sort by BSN or Title? BSN is string, maybe sort by start_time? let's just sort by BSN for stability
    scrapers_list.sort(key=lambda x: x[0]) 

    start = (page - 1) * limit
    end = start + limit
    paginated_items = scrapers_list[start:end]
    paginated_scrapers = dict(paginated_items)
    
    # Get System Metrics
    cpu_usage = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()

    return {
        "curr_status": Status.curr_status,
        "scrapers_status": paginated_scrapers,
        "page_count": Status.page_count,
        "tasks_count": len(Status.tasks),
        "total_scrapers_count": len(Status.scrapers),
        "filtered_count": len(scrapers_list),
        "page": page,
        "limit": limit,
        "system_metrics": {
            "cpu_usage": cpu_usage,
            "memory_usage": mem.percent,
            "memory_total": mem.total,
            "memory_available": mem.available,
            "memory_used": mem.used
        }
    }
