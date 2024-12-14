from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import json

class GitHubEvent(BaseModel):
    id: str
    type: str
    created_at: datetime
    repository: str
    raw_data: Dict

    # Method to convert to Redis hash format
    def to_redis_hash(self) -> dict:
        return {
            'id': self.id,
            'type': self.type,
            'created_at': self.created_at.isoformat(),
            'repository': self.repository,
            'raw_data': json.dumps(self.raw_data)
        }
    
    # Class method to create from Redis hash
    @classmethod
    def from_redis_hash(cls, hash_data: dict) -> 'GitHubEvent':
        return cls(
            id=hash_data['id'],
            type=hash_data['type'],
            created_at=datetime.fromisoformat(hash_data['created_at']),
            repository=hash_data['repository'],
            raw_data=json.loads(hash_data['raw_data'])
        )

class EventResponse(BaseModel):
    """
    Our standardized response format for event-related endpoints.
    Includes metadata about the request along with the events.
    """
    events: List[GitHubEvent]
    count: int
    timestamp: datetime
    event_types: List[str]