from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class GitHubEventBase(BaseModel):
    id: str
    type: str
    created_at: datetime
    repository: str
    raw_data: Dict

class GitHubEventCreate(GitHubEventBase):
    pass

class EventResponse(BaseModel):
    """
    Our standardized response format for event-related endpoints.
    Includes metadata about the request along with the events.
    """
    events: List[GitHubEventBase]
    count: int
    timestamp: datetime
    event_types: List[str]