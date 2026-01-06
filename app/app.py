from fastapi import FastAPI
import psutil
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from src.status import Status
from src import utils
from src.main import main as scraper_main
import asyncio

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
    filtered_items = []
    q = q.lower().strip()
    
    # Create list of matching items first
    for bsn, status in Status.scrapers_status.items():
        # Ensure status is a dict
        if not isinstance(status, dict):
            continue
            
        title = status.get('theme_title', '')
        if not q or q in str(bsn).lower() or q in title.lower():
            filtered_items.append((bsn, status))

    # Sort by BSN
    filtered_items.sort(key=lambda x: x[0]) 
    
    # Calculate active scrapers count (before pagination)
    active_scrapers_count = sum(
        1 for _, status in filtered_items 
        if isinstance(status, dict) and status.get('post_status') != 'none'
    )
    
    # Pagination
    total_filtered = len(filtered_items)
    start = (page - 1) * limit
    end = start + limit
    paginated_items = filtered_items[start:end]
    
    # Convert back to dict for response
    paginated_scrapers = dict(paginated_items)
    
    # Get System Metrics
    cpu_usage = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()

    return {
        "curr_status": Status.curr_status,
        "scrapers_status": paginated_scrapers,
        "page_count": Status.page_count,
        "tasks_count": len(Status.tasks),
        "total_scrapers_count": len(Status.scrapers_status),
        "active_scrapers_count": active_scrapers_count,
        "filtered_count": total_filtered,
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

@app.post('/api/refresh')
async def refresh_scraper():
    if utils.TOP_SCRAPE_TASK and not utils.TOP_SCRAPE_TASK.done():
        return {"status": "error", "message": "Scraper is already running"}
    
    utils.TOP_SCRAPE_TASK = asyncio.create_task(scraper_main())
    return {"status": "success", "message": "Scraper started"}
