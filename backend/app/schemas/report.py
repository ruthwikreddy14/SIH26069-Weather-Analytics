"""
Pydantic schemas for weather report API.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class GPSCoordinates(BaseModel):
    """GPS coordinates."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class ReportCreate(BaseModel):
    """Schema for creating a new weather report (citizen form submission)."""
    
    event_type: str = Field(
        ...,
        description="Type of weather event",
        pattern="^(rainfall|flooding|thunderstorm|heatwave|fog|dust_storm|strong_wind)$"
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Description of the weather event"
    )
    city: str = Field(..., min_length=2, max_length=100, description="City name")
    state: str = Field(..., min_length=2, max_length=100, description="State name")
    gps: Optional[GPSCoordinates] = Field(None, description="Optional GPS coordinates")
    media_files: Optional[List[str]] = Field(
        None,
        description="Optional list of base64-encoded media files (future: use MinIO upload)"
    )
    
    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Ensure description is not empty after stripping whitespace."""
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()
    
    @field_validator("event_type")
    @classmethod
    def normalize_event_type(cls, v: str) -> str:
        """Normalize event type to lowercase with underscores."""
        return v.lower().replace(" ", "_")


class ReportSubmitResponse(BaseModel):
    """Response after submitting a report."""
    
    report_id: UUID = Field(..., description="UUID of the created report")
    status: str = Field(..., description="Initial status (pending/unverified)")
    message: str = Field(..., description="Success message")


class LocationInfo(BaseModel):
    """Location information for a report."""
    
    lat: Optional[float] = None
    lon: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    location_source: Optional[str] = None
    location_confidence: Optional[str] = None


class ReportResponse(BaseModel):
    """Schema for returning report details."""
    
    id: str  # Can be UUID or string for test compatibility
    event_type: Optional[str] = None
    description: str
    location: Optional[LocationInfo] = None
    verification_status: Optional[str] = "unverified"
    confidence_score: Optional[float] = None
    reported_at: datetime
    media_urls: Optional[List[str]] = None
    signals: Optional[dict] = None
    
    class Config:
        from_attributes = True


class ReportDetail(BaseModel):
    """Detailed report response including all fields."""
    
    id: str  # Can be UUID or string for test compatibility
    source_type: str
    event_type: Optional[str] = None
    description: str
    location: Optional[LocationInfo] = None
    city: Optional[str] = None
    state: Optional[str] = None
    verification_status: Optional[str] = "unverified"
    confidence_score: Optional[float] = None
    signals: Optional[dict] = None
    cluster_id: Optional[str] = None  # Can be UUID or string
    admin_override: bool = False
    admin_notes: Optional[str] = None
    reported_at: datetime
    ingested_at: datetime
    verified_at: Optional[datetime] = None
    media_urls: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class ReportFilter(BaseModel):
    """Query parameters for filtering reports."""
    
    date_from: Optional[datetime] = Field(None, description="Filter reports from this date")
    date_to: Optional[datetime] = Field(None, description="Filter reports until this date")
    event_type: Optional[List[str]] = Field(
        None,
        description="Filter by event types (comma-separated: flooding,rainfall)"
    )
    state: Optional[str] = Field(None, description="Filter by state")
    status: Optional[List[str]] = Field(
        None,
        description="Filter by verification status (verified,disputed,fake,unverified)"
    )
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class ReportListResponse(BaseModel):
    """Response for list of reports with pagination."""
    
    reports: List[ReportResponse]
    total: int = Field(..., description="Total number of reports matching filters")
    limit: int
    offset: int
