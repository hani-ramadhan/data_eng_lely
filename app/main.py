from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import uvicorn 
from .services.event_service import EventService
from .models.github_events import EventResponse
import asyncio


# Define the lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create background task for event collection
    event_collection_task = asyncio.create_task(EventService.start_event_collection())
    yield
    # Shutdown: Cancel the background task
    event_collection_task.cancel()
    try:
        await event_collection_task
    except asyncio.CancelledError:
        # Task was canceled, cleanup completed
        pass

# Create FastAPI application instance
app = FastAPI(
    title="GitHub Events API",
    description="A simple API to monitor GitHub events",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy",
            "message": "GitHub Events API is running",
            "supported_event_types": list(EventService.ALLOWED_EVENT_TYPES)
    }

@app.get("/events", response_model=EventResponse)
async def get_events(event_type: Optional[str] = None):
    """
    Fetch GitHub events with optional type filtering.
    
    Args:
        event_type: Optional filter for specific event types (WatchEvent, PullRequestEvent, IssuesEvent)
        
    Returns:
        EventResponse containing the filtered events and metadata
    """
    return await EventService.fetch_events(event_type)

@app.get("/metrics/event-count/{offset}")
async def get_event_counts(offset: int):
    """
    Get event counts by type for the specified time offset (minutes)
    """
    if offset <= 0:
        raise HTTPException(
            status_code=400,
            detail="Offset must be greater than 0"
        )
    return await EventService.count_events_by_type(offset)

@app.get("/storage/stats")
async def get_storage_stats():
    """Get current storage statistics"""
    return {
        "total_events_stored": len(EventService._event_storage),
        "last_fetch_time": EventService._last_fetch_time,
        "fetch_interval": EventService.FETCH_INTERVAL_SECONDS
    }

@app.get("/metrics/pr-time-gap")
async def get_pr_time_gap(repository: str):
    """
    Use as: /metrics/pr-time-gap?repository=owner/repo
    """
    return await EventService.calculate_pr_time_gap(repository)

# Modified to work better in production
if __name__ == "__main__":
    # Don't use reload in production
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Allows external access
        port=8000,
        workers=4  # Multiple workers for better performance
    )