from typing import List, Optional, Dict, Set, Tuple
import os
import httpx
from ..models.github_events import GitHubEvent
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from dotenv import load_dotenv
import asyncio
import json, csv
import redis

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
    redis_client = redis.Redis(
        host='localhost', 
        port=6379, 
        decode_responses=True)
    
    FETCH_INTERVAL_SECONDS = 1 # Fetch every 1 seconds


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
    
    @classmethod
    async def start_event_collection(cls):
        """Background task to continuously collect events"""
        while True:
            await cls.store_events()
            await asyncio.sleep(cls.FETCH_INTERVAL_SECONDS)

    @classmethod
    async def store_events(cls):
        """Fetch and store GitHub events with Redis"""
        try:
            current_time = datetime.now(timezone.utc)
            all_events = []
            next_url = 'https://api.github.com/events'
            new_events_count = 0
            duplicate_count =  0
            
            # Fetch events (keeping existing fetch logic...)
            async with httpx.AsyncClient() as client:
                i = 0
                while next_url and i < 5:
                    response = await client.get(next_url, headers=cls.get_headers())
                    response.raise_for_status()
                    
                    page_events = response.json()
                    all_events.extend(page_events)

                    if not page_events:
                        break

                    all_events.extend(page_events)
                    
                    # # Check rate limit
                    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                    if remaining < 200:
                        print(f"Remaining API calls: {remaining}")
                    
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
                    i += 1

            _last_fetch_time = current_time
            
            # Process and store events
            for event_data in all_events:
                if event_data['type'] not in cls.ALLOWED_EVENT_TYPES:
                    continue

                event_id = event_data['id']
                cls._event_storage = cls._event_storage +1
                
                # Check for duplicates using Redis SET
                if cls.redis_client.sismember('event_ids', event_data['id']):
                    duplicate_count += 1
                    continue

                # Create Pydantic model
                event = GitHubEvent(
                    id=event_data['id'],
                    type=event_data['type'],
                    created_at=datetime.fromisoformat(event_data['created_at'].replace('Z', '+00:00')),
                    repository=event_data['repo']['name'],
                    raw_data=event_data
                )

                # Store in Redis using pipeline for atomic operations
                with cls.redis_client.pipeline() as pipe:
                    # Store full event data as hash
                    pipe.hset(
                        f"event:{event.id}",
                        mapping=event.to_redis_hash()
                    )
                    
                    # Add to event IDs set for duplicate checking
                    pipe.sadd('event_ids', event.id)
                    
                    # Add to time-based sorted set
                    pipe.zadd(
                        'events_by_time',
                        {event.id: event.created_at.timestamp()}
                    )
                    
                    # Add to type-based sorted set
                    pipe.zadd(
                        f"events:{event.type}",
                        {event.id: event.created_at.timestamp()}
                    )
                    
                    # For pull requests, add to repository-specific set
                    if event.type == 'PullRequestEvent':
                        pipe.zadd(
                            f"pull_requests:{event.repository}",
                            {event.id: event.created_at.timestamp()}
                        )

                        # Increment PR count for repository
                        pipe.zincrby('pr_repository_counts', 1, event.repository)
                    
                    # Set TTL for event data (24 hours)
                    pipe.expire(f"event:{event.id}", 86400)
                    
                    # Execute all commands
                    pipe.execute()
                
                new_events_count += 1

            # Clean up old events (older than 24 hours)
            cutoff_time = current_time - timedelta(hours=24)
            old_events = cls.redis_client.zrangebyscore(
                'events_by_time',
                '-inf',
                cutoff_time.timestamp()
            )
            
            if old_events:
                with cls.redis_client.pipeline() as pipe:
                    for event_id in old_events:
                        pipe.delete(f"event:{event_id}")
                        pipe.srem('event_ids', event_id)
                        pipe.zrem('events_by_time', event_id)
                    pipe.execute()

            print(f"summary: ")
            print(f"Total stored events: {cls._event_storage}")
        except Exception as e:
            print(f"Error storing events: {str(e)}")
            raise
        except Exception as e:
            print(f"Error storing events: {str(e)}")
    
    @classmethod
    async def count_events_by_type(cls, offset: int) -> dict:
        """Count events by type for events within the last X minutes"""
        try:
            current_time = datetime.now(timezone.utc)
            min_time = (current_time - timedelta(minutes=offset)).timestamp()
            max_time = (current_time).timestamp()

            counts = {}
            for event_type in cls.ALLOWED_EVENT_TYPES:
                count = cls.redis_client.zcount(
                    f"events:{event_type}",
                    min_time,
                    max_time
                )
                counts[event_type] = count
                
            return {
                "counts": counts,
                "total_monitored_events": sum(counts.values()),
                "time_window": f"Last {offset} minutes",
                "timestamp": current_time,
                "monitored_event_types": list(cls.ALLOWED_EVENT_TYPES)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to count events: {str(e)}"
            )

    @classmethod
    async def calculate_pr_time_gap(cls, repository: str) -> dict:
        """Calculate average time between pull requests for a repository"""
        try:
            # Get all PR timestamps for repository

            repo_with_multiple_pr = cls.get_repo_with_multiple_pr()
            
            pr_data = cls.redis_client.zrange(
                f"pull_requests:{repository}",
                0,
                -1,
                withscores=True
            )
            
            if len(pr_data) < 2:
                return {
                    "repository": repository,
                    "average_time_between_prs": None,
                    "total_prs": len(pr_data),
                    "error": "Not enough pull requests to calculate average"
                }
            
            # Calculate time gaps
            timestamps = sorted([score for _, score in pr_data])
            gaps = []
            for i in range(1, len(timestamps)):
                gap = (timestamps[i] - timestamps[i-1]) / 60  # Convert to minutes
                gaps.append(gap)
            
            avg_gap = sum(gaps) / len(gaps)
            
            return {
                "repository": repository,
                "average_time_between_prs": round(avg_gap, 2),
                "total_prs": len(pr_data),
                "first_pr_time": datetime.fromtimestamp(timestamps[0], tz=timezone.utc).isoformat(),
                "last_pr_time": datetime.fromtimestamp(timestamps[-1], tz=timezone.utc).isoformat(),
                "min_gap": round(min(gaps), 2),
                "max_gap": round(max(gaps), 2),
                "unit": "minutes"
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to calculate PR time gap: {str(e)}"
            )
        
    @classmethod
    async def get_repo_with_multiple_pr(cls, min_prs: int = 2) -> Dict:
        # Get all PR timestamps for repository
        try:
            pr_data_count = cls.redis_client.zrangebyscore(
                'pr_repository_counts', 
                min_prs,
                '+inf',
                withscores=True
            )

            return pr_data_count
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list out repo with multiple PRs: {str(e)}"
            )
        
