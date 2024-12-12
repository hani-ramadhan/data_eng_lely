from typing import Optional
from fastapi import FastAPI, HTTPException
import httpx
import uvicorn 
from .services.event_service import EventService
from .models.github_events import EventResponse



# Create FastAPI application instance
app = FastAPI(
    title="GitHub Events API",
    description="A simple API to monitor GitHub events",
    version="0.1.0"
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

# Modified to work better in production
if __name__ == "__main__":
    # Don't use reload in production
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Allows external access
        port=8000,
        workers=4  # Multiple workers for better performance
    )