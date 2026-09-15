from pydantic import BaseModel
from typing import Dict, Any


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str
    app_name: str
    version: str
    database: str
    redis: str
    details: Dict[str, Any] = {}
