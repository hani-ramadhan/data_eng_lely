from fastapi import FastAPI
import httpx

# Create FastAPI application instance
app = FastAPI(
    title="GitHub Events API",
    description="A simple API to monitor GitHub events",
    version="0.1.0"
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "message": "GitHub Events API is running"}

@app.get("/events")
async def get_events():
    """Fetch GitHub events"""
    async with httpx.AsyncClient() as client:
        response = await client.get('https://api.github.com/events')
        return response.json()