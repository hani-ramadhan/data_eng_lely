from typing import List, Optional
import os
import httpx
from ..models.github_events import GitHubEvent, EventResponse
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()


class EventService:
    """
    Handles all GitHub event-related operations.
    This service layer helps separate our business logic from our API routes.
    """
    ALLOWED_EVENT_TYPES = {'WatchEvent', 'PullRequestEvent', 'IssuesEvent'}
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

    @staticmethod
    def get_headers():
        """Get headers for GitHub API requests"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
        }
        if EventService.GITHUB_TOKEN:
            headers['Authorization'] = f'token {EventService.GITHUB_TOKEN}'
        return headers
    
    @staticmethod
    async def fetch_events(event_type: Optional[str] = None) -> EventResponse:
        """
        Fetches GitHub events and filters them based on event type if specified 
        with authenticiation.
        
        Args:
            event_type: Optional filter for specific event types
            
        Returns:
            EventResponse containing filtered events and metadata
        """
        if event_type and event_type not in EventService.ALLOWED_EVENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Event type must be one of {EventService.ALLOWED_EVENT_TYPES}"
            )
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    'https://api.github.com/events',
                    headers=EventService.get_headers()
                )
                response.raise_for_status()

               # Check rate limit information
                rate_limit = {
                    'limit': response.headers.get('X-RateLimit-Limit'),
                    'remaining': response.headers.get('X-RateLimit-Remaining'),
                    'reset': response.headers.get('X-RateLimit-Reset')
                }

                
                print(f"Rate limit info: {rate_limit}")



                events_data = response.json()
                
                # Filter events first
                filtered_events  = [
                    event for event in events_data
                    if not event_type or event['type'] == event_type
                ]
                
                
                # Convert filtered events to GitHubEvent models
                events = [GitHubEvent(**event) for event in filtered_events]
                
                # Get unique event types from the original event dictionaries
                event_types = list(set(event['type'] for event in filtered_events))


                return EventResponse(
                    events=events,
                    count=len(events),
                    timestamp=datetime.now(),
                    event_types=event_types
                )
                
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"GitHub API error: {e.response.text}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch events: {str(e)}"
                )
        
    @staticmethod
    async def count_events_by_type(offset_minutes: int) -> dict:
        """
        Count events by type for events within the last X minutes
        
        Args:
            offset_minutes: Look back time in minutes
            
        Returns:
            Dictionary with event types as keys and counts as values
        """
        try:
            # Get all events first
            response = await EventService.fetch_events()
            events = response.events
            
            # Calculate cutoff time
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
            
            # Filter and count events
            filtered_events = [
                event for event in events
                if event.created_at.replace(tzinfo=timezone.utc) > cutoff_time and
                event.type in EventService.ALLOWED_EVENT_TYPES
            ]


            # Initialize counts with 0 for all allowed event types
            counts = {event_type: 0 for event_type in EventService.ALLOWED_EVENT_TYPES}
             
            # Count only allowed event types
            for event in filtered_events:
                    counts[event.type] += 1
               
            return {
                "counts": counts,
                "total": len(filtered_events),
                "time_window": f"Last {offset_minutes} minutes",
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to count events: {str(e)}"
            )
        
