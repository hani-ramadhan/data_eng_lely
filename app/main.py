from datetime import datetime
from tempfile import template
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

from app.services.monitoring_charts import GithubMonitoringCharts
from app.services.historical_data_service import HistoricalDataService 
from app.services.event_service import EventService
from app.models.github_events import EventResponse
import asyncio

from jinja2 import Environment, FileSystemLoader

from fastapi.templating import Jinja2Templates





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

templates = Jinja2Templates(directory="./app/templates")



@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy",
            "message": "GitHub Events API is running",
            "supported_event_types": list(EventService.ALLOWED_EVENT_TYPES)
    }

@app.get("/metrics/event-count/{offset}")
async def get_event_counts(offset: int):
    """
    Get event counts by type {PullRequest, Issue, Watch} for the specified time offset (minutes)
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

@app.get("/multiple-pr")
async def get_multiple_pr():
    return await EventService.get_repo_with_multiple_pr()


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, repository: str = "example/repo"):
    """Serve the monitoring dashboard"""
    try:

        # Store current metrics
        await HistoricalDataService.store_metrics_snapshot(EventService.count_events_by_type)
        
        # # Get current event data
        # current_data = await EventService.count_events_by_type(10)
        
        # Get total data
        all_data = await EventService.count_events_by_type(-1)

        # Get historical data (last 15 minutes)
        historical_data = await HistoricalDataService.get_historical_data()
        
        # Get PR data for specified repository
        # # pr_data = await EventService.calculate_pr_time_gap(repository)
        # historical_pr_data = await HistoricalDataService.get_historical_data(repository)
        
        # Get top repositories with PR counts
        top_repos = await EventService.get_repo_with_multiple_pr(min_prs=2)
        # print(top_repos[-10:])
        # Get PR time gap for each top repository
        pr_stats = []

        for repo, count in top_repos[-10:]:  # Limit to top 10 repos
            stats = await EventService.calculate_pr_time_gap(repo)
            if stats.get('average_time_between_prs'):  # Only add if we have valid average
                pr_stats.append({
                    'repository': repo,
                    'pr_count': count,
                    'avg_time': stats['average_time_between_prs']
                })
        
        # Sort by PR count descending
        pr_stats.sort(key=lambda x: x['pr_count'], reverse=True)

        # Generate charts
        charts = {
            'total_events': GithubMonitoringCharts.create_total_events_chart(historical_data),
            'distribution': GithubMonitoringCharts.create_distribution_chart(historical_data),
            'pr_comparison': GithubMonitoringCharts.create_pr_comparison_chart(pr_stats),
            # 'pr_time': GithubMonitoringCharts.create_pr_time_chart(historical_pr_data, repository)
        
        }
        
        # Calculate current totals
        current_counts = all_data['counts']
        total_events = sum(current_counts.values())
        
        return templates.TemplateResponse(
            "monitoring.html",
            {
                "request": request,
                "charts": charts,
                "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_events": total_events,
                "watch_events": current_counts.get('WatchEvent', 0),
                "issue_events": current_counts.get('IssuesEvent', 0),
                "pr_events": current_counts.get('PullRequestEvent', 0),
                "current_repository": repository
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e)
            }
        )

@app.post("/update-repository")
async def update_repository(repository: str = Form(...)):
    """Handle repository update form submission"""
    return RedirectResponse(url=f"/dashboard?repository={repository}", status_code=303)


# Modified to work better in production
if __name__ == "__main__":
    # Don't use reload in production
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Allows external access
        port=8000,
        workers=4  # Multiple workers for better performance
    )