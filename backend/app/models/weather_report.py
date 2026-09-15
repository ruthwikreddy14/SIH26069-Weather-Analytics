from sqlalchemy import Column, String, Float, Boolean, Text, ARRAY, TIMESTAMP, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

from app.core.database import Base


class WeatherReport(Base):
    """Weather report submitted from various sources."""
    
    __tablename__ = "weather_reports"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source information
    source_type = Column(String(50), nullable=False)  # 'twitter' | 'citizen_form' | 'imd_api' | 'openweather'
    source_id = Column(String(255), nullable=True)  # tweet_id, form_submission_id, etc.
    
    # Content
    raw_text = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=True)  # rainfall, flooding, thunderstorm, etc.
    event_type_confidence = Column(Float, nullable=True)
    
    # Location - using Geography for PostGIS spatial queries
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    location_source = Column(String(50), nullable=True)  # 'gps_verified' | 'text_inferred' | 'gps_suspicious'
    location_confidence = Column(String(20), nullable=True)  # 'high' | 'medium' | 'low'
    
    # Media
    media_urls = Column(ARRAY(Text), nullable=True)  # Array of MinIO URLs
    image_hashes = Column(ARRAY(Text), nullable=True)  # Array of pHash strings
    
    # Verification
    verification_status = Column(String(20), nullable=True, default='unverified')  # 'verified' | 'disputed' | 'unverified' | 'fake'
    confidence_score = Column(Float, nullable=True)
    signals = Column(JSONB, nullable=True)  # Stores all three signal outputs
    
    # Clustering
    cluster_id = Column(UUID(as_uuid=True), ForeignKey('event_clusters.id'), nullable=True)
    
    # Admin actions
    admin_override = Column(Boolean, default=False)
    admin_notes = Column(Text, nullable=True)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey('admin_users.id'), nullable=True)
    
    # Timestamps
    reported_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    ingested_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('confidence_score >= 0.0 AND confidence_score <= 1.0', name='valid_confidence'),
    )


class EventCluster(Base):
    """Cluster of duplicate/similar weather reports."""
    
    __tablename__ = "event_clusters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=True)
    canonical_text = Column(Text, nullable=True)  # Representative text for cluster
    centroid = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)  # Geographic center
    report_count = Column(Float, default=1)  # Changed to Float to avoid int issues
    first_reported_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_reported_at = Column(TIMESTAMP(timezone=True), nullable=True)


class VerificationLog(Base):
    """Log of verification steps performed on reports."""
    
    __tablename__ = "verification_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey('weather_reports.id'), nullable=False)
    verification_step = Column(String(100), nullable=False)  # 'ground_truth_check', 'image_hash', etc.
    result = Column(JSONB, nullable=True)
    executed_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class AdminUser(Base):
    """Admin users for the platform."""
    
    __tablename__ = "admin_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
