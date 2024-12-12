from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class GitHubEvent(BaseModel):
    """
    Represents a GitHub event with essential fields we're interested in.
    We use Pydantic for automatic data validation and serialization.
    """
    id: str
    type: str
    created_at: datetime
    repo: dict
    actor: dict

class EventResponse(BaseModel):
    """
    Our standardized response format for event-related endpoints.
    Includes metadata about the request along with the events.
    """
    events: List[GitHubEvent]
    count: int
    timestamp: datetime
    event_types: List[str]