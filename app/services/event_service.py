from typing import List, Optional, Dict, Set, Tuple
import os
import httpx
from ..models.github_events import GitHubEventCreate
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from dotenv import load_dotenv
import asyncio
import json, csv
from pathlib import Path

load_dotenv()

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class EventService:
    """
    Handles all GitHub event-related operations.
    This service layer helps separate our business logic from our API routes.
    """
    # Class variables for storage
    _event_storage: List[Dict] = []
    _last_fetch_time: Optional[datetime] = None
    _oldest_event_id: Optional[str] = None
    _oldest_event_time: Optional[datetime] = None
    _event_ids: Set[Tuple[str, datetime]] = set()
    CLEANUP_MINUTES = 30
    
    FETCH_INTERVAL_SECONDS = 1 # Fetch every 1 seconds


    ALLOWED_EVENT_TYPES = {'WatchEvent', 'PullRequestEvent', 'IssuesEvent'}
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')


    @classmethod
    async def start_event_collection(cls):
        """Background task to continuously collect events"""
        while True:
            await cls.store_events()
            await asyncio.sleep(cls.FETCH_INTERVAL_SECONDS)

    @classmethod
    async def store_events(cls):
        """Fetch and store GitHub events"""
        try:
            current_time = datetime.now(timezone.utc)
            all_events = []
            next_url = 'https://api.github.com/events'
            
            # Track current batch's oldest event
            batch_oldest_time = None

            
            # Fetch new events
            async with httpx.AsyncClient() as client:
                i = 0
                while next_url and i < 4:
                    response = await client.get(
                        next_url,
                        headers=cls.get_headers()
                    )
                    response.raise_for_status()

                    i = i + 1
                    
                    fetched_time = datetime.now(timezone.utc)
                    # Get events from current page
                    page_events = response.json()

                    if not page_events:
                        break

                    # Track oldest event in this batch
                    batch_oldest_event = page_events[-1]
                    batch_oldest_time = datetime.fromisoformat(
                        batch_oldest_event['created_at'].replace('Z', '+00:00')
                    )

                    # If this is first run, just store events
                    if cls._oldest_event_time is None:
                        cls._oldest_event_time = batch_oldest_time
                        cls._oldest_event_id = batch_oldest_event['id']
                        all_events.extend(page_events)
                    else:
                        # Check if we've missed events
                        time_gap = cls._oldest_event_time - batch_oldest_time
                        if time_gap > timedelta(seconds=cls.FETCH_INTERVAL_SECONDS):  # Add buffer
                            print(f"WARNING: Potential data gap detected!")
                            print(f"Time gap: {time_gap.total_seconds()} seconds")
                            print(f"Previous oldest: {cls._oldest_event_time}")
                            print(f"Current oldest: {batch_oldest_time}")


                    # Update tracking
                    cls._oldest_event_time = batch_oldest_time
                    cls._oldest_event_id = batch_oldest_event['id']

                    for event in page_events:
                        event['fetched_at'] = fetched_time
                        event['page'] = i
                        event['url'] = next_url

                    all_events.extend(page_events)
                    
                    # # Check rate limit
                    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                    # print(f"Remaining API calls: {remaining}")
                    
                    # Get next page URL from Link header
                    next_url = None
                    link_header = response.headers.get('Link', '')
                    
                    for link in link_header.split(', '):
                        if 'rel="next"' in link:
                            next_url = link[link.index('<') + 1:link.index('>')]
                        
                    
                    if remaining < 10:  # Safety margin
                        print("Getting close to rate limit, stopping pagination")
                        break
                        
                    if len(all_events) >= 1000:  # Example limit
                        print("Reached maximum events limit")
                        break

            # Clean old IDs first (older than 30 minutes)
            cls._event_ids = {
                (event_id, timestamp) 
                for event_id, timestamp in cls._event_ids
                if (current_time - timestamp) < timedelta(minutes=cls.CLEANUP_MINUTES)
            }

            # Get current IDs for checking
            current_ids = {event_id for event_id, _ in cls._event_ids}  

            # # Process and store new events
            for event_data in all_events:

                if event_data['type'] not in EventService.ALLOWED_EVENT_TYPES:
                    continue

                # Skip if ID exists
                if event_data['id'] in current_ids:
                    continue

                # Add to hashset with current timestamp
                cls._event_ids.add((event_data['id'], 
                                    datetime.fromisoformat(event_data['created_at'].replace('Z', '+00:00'))))
        
                current_ids.add(event_data['id'])

                event_create = GitHubEventCreate(
                    id=event_data['id'],
                    type=event_data['type'],
                    created_at=datetime.fromisoformat(event_data['created_at'].replace('Z', '+00:00')),
                    repository=event_data['repo']['name'],
                    raw_data=event_data
                )

                # stored_event = {
                #     'id':event_create.id,
                #     'data': event_data,
                #     'type': event_create.type,
                #     'created_at': event_create.created_at,
                #     'stored_at': current_time,
                #     'fetched_at': event_data['fetched_at'],
                #     'page': event_data['page'],
                #     'url':  event_data['url']

                # }
                # cls._event_storage.append(stored_event)

            # # # Process and store new events
            # for event_data in all_events:

            #     if event_data['type'] not in EventService.ALLOWED_EVENT_TYPES:
            #         continue
                
                event_create = GitHubEventCreate(
                    id=event_data['id'],
                    type=event_data['type'],
                    created_at=datetime.fromisoformat(event_data['created_at'].replace('Z', '+00:00')),
                    repository=event_data['repo']['name'],
                    raw_data=event_data,
                )

                stored_event = {
                    'id':event_create.id,
                    'data': event_data,
                    'type': event_create.type,
                    'created_at': event_create.created_at,
                    'stored_at': current_time

                }

                cls._event_storage.append(stored_event)
            cls.save_to_csv()

            # Clean up old events (keep last 24 hours)
            cutoff_time = current_time - timedelta(hours=24)
            cls._event_storage = [
                event for event in cls._event_storage
                if event['stored_at'] > cutoff_time
            ]

            cls._last_fetch_time = current_time
            print(f"Processed {len(all_events)} events. Total events in storage: {len(cls._event_storage)}")

        except Exception as e:
            print(f"Error storing events: {str(e)}")

    @classmethod
    async def calculate_pr_time_gap(cls, repository: str) -> dict:
        """
        Calculate average time between pull requests for a given repository
        
        Args:
            repository: Full repository name (e.g., 'owner/repo')
            
        Returns:
            Dictionary containing average time gap and related statistics
        """
        # Filter PullRequestEvent for the given repository
        pr_events = [
            event for event in cls._event_storage
            if (event['type'] == 'PullRequestEvent' and 
                event['data']['repo']['name'] == repository)  # Only count PR openings
        ]
        
        if len(pr_events) < 2:
            return {
                "repository": repository,
                "average_time_between_prs": None,
                "total_prs": len(pr_events),
                "error": "Not enough pull requests to calculate average"
            }
            
        # Sort events by creation time
        pr_events.sort(key=lambda x: x['created_at'])
        
        # Calculate time differences between consecutive PRs
        sum_time_gaps = 0
        for i in range(1, len(pr_events)):
            current_pr = pr_events[i]['created_at']
            previous_pr = pr_events[i-1]['created_at']
            gap = (current_pr - previous_pr).total_seconds() 
            sum_time_gaps += gap
        
        # Calculate statistics
        avg_gap = sum_time_gaps/(len(pr_events)-1)
        
        return {
            "repository": repository,
            "average_time_between_prs": round(avg_gap, 2),  # In seconds
            "total_prs": len(pr_events),
            "first_pr_time": pr_events[0]['created_at'].isoformat(),
            "last_pr_time": pr_events[-1]['created_at'].isoformat(),
            # "min_gap": round(min(time_gaps), 2),
            # "max_gap": round(max(time_gaps), 2),
            "unit": "seconds"
        }

    @staticmethod
    def get_headers():
        """Get headers for GitHub API requests"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
        }
        if EventService.GITHUB_TOKEN:
            headers['Authorization'] = f'token {EventService.GITHUB_TOKEN}'
        return headers
    
    @classmethod
    def save_to_csv(cls):
        """
        Save event data to CSV file with specific fields
        """
        # Create events directory if it doesn't exist
        Path("events").mkdir(exist_ok=True)
        
        # Define CSV headers
        headers = ['id', 'created_at', 'repository', 'event_type','stored_at','fetched_at','page','url']
        
        # Check if file exists to determine if we need to write headers
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        csv_path = f"events/storage_{current_time}.csv"

        
 
        
        # Open file in append mode
        with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()

            for event in cls._event_storage:
                row_data = {
                    'id': event['id'],
                    'created_at': event['created_at'].isoformat(),
                    'repository': event['data']['repo']['name'],
                    'event_type': event['type'],
                    'stored_at':event['stored_at']
                }
                writer.writerow(row_data)
                
        print(f"Successfully saved {len(cls._event_storage)} events to {csv_path}")
        
   
    # @staticmethod
    # async def fetch_events(event_type: Optional[str] = None) -> EventResponse:
    #     """
    #     Fetches GitHub events and filters them based on event type if specified 
    #     with authenticiation.
        
    #     Args:
    #         event_type: Optional filter for specific event types
            
    #     Returns:
    #         EventResponse containing filtered events and metadata
    #     """
    #     if event_type and event_type not in EventService.ALLOWED_EVENT_TYPES:
    #         raise HTTPException(
    #             status_code=400,
    #             detail=f"Event type must be one of {EventService.ALLOWED_EVENT_TYPES}"
    #         )
            
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             response = await client.get(
    #                 'https://api.github.com/events?page=100',
    #                 headers=EventService.get_headers()
    #             )
    #             response.raise_for_status()

    #            # Check rate limit information
    #             rate_limit = {
    #                 'limit': response.headers.get('X-RateLimit-Limit'),
    #                 'remaining': response.headers.get('X-RateLimit-Remaining'),
    #                 'reset': response.headers.get('X-RateLimit-Reset')
    #             }

                
    #             print(f"Rate limit info: {rate_limit}")
                



    #             events_data = response.json()
                
    #             # Filter events first
    #             filtered_events  = [
    #                 event for event in events_data
    #                 if not event_type or event['type'] == event_type
    #             ]
                
                
    #             # Convert filtered events to GitHubEvent models
    #             events = [GitHubEvent(**event) for event in filtered_events]
                
    #             # Get unique event types from the original event dictionaries
    #             event_types = list(set(event['type'] for event in filtered_events))


    #             return EventResponse(
    #                 events=events,
    #                 count=len(events),
    #                 timestamp=datetime.now(),
    #                 event_types=event_types
    #             )
                
    #         except httpx.HTTPStatusError as e:
    #             raise HTTPException(
    #                 status_code=e.response.status_code,
    #                 detail=f"GitHub API error: {e.response.text}"
    #             )
    #         except Exception as e:
    #             raise HTTPException(
    #                 status_code=500,
    #                 detail=f"Failed to fetch events: {str(e)}"
    #             )
        
    @classmethod
    async def count_events_by_type(cls, offset_minutes: int) -> dict:
        """
        Count events by type for events within the last X minutes
        
        Args:
            offset_minutes: Look back time in minutes
            
        Returns:
            Dictionary with event types as keys and counts as values
        """
        try:
            # Get all events first
            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(minutes=offset_minutes)

            print(cls._event_storage[-5:])
            
            # Filter and count events
            filtered_events = [
                event for event in cls._event_storage
                if event['created_at'].replace(tzinfo=timezone.utc) > cutoff_time
            ]


            # Initialize counts with 0 for all allowed event types
            counts = {event_type: 0 for event_type in EventService.ALLOWED_EVENT_TYPES}
             
            # Count only allowed event types
            for event in filtered_events:
                    counts[event['type']] += 1
               
            return {
                "counts": counts,
                               "total_monitored_events": sum(counts.values()),
                "time_window": f"Last {offset_minutes} minutes",
                "timestamp": current_time,
                "monitored_event_types": list(cls.ALLOWED_EVENT_TYPES),
                "storage_stats": {
                    "total_events_stored": len(cls._event_storage),
                    "last_fetch_time": cls._last_fetch_time
                }
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to count events: {str(e)}"
            )
        
