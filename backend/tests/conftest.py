"""
Shared test fixtures for the backend test suite.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import Column, String, Float, Text, ARRAY, TIMESTAMP, ForeignKey, event
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
import json
from datetime import datetime

# Test database URL (in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create a separate Base for testing (without Geography types)
TestBase = declarative_base()


class WeatherReportTest(TestBase):
    """Simplified WeatherReport model for testing (without PostGIS)."""
    
    __tablename__ = "weather_reports"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = Column(String(50), nullable=False, default='web')
    source_id = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=False, default='')
    description = Column(Text, nullable=True)  # Added for pipeline tests
    event_type = Column(String(50), nullable=True)
    event_type_confidence = Column(Float, nullable=True)
    
    # Simplified location (no Geography type for SQLite)
    location = None  # Set to None for compatibility
    latitude = Column(Float, nullable=True)  # Added for pipeline tests
    longitude = Column(Float, nullable=True)  # Added for pipeline tests
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    location_source = Column(String(50), nullable=True)
    location_confidence = Column(String(20), nullable=True)
    
    images = Column(Text, nullable=True)  # Added for pipeline tests - JSON string
    media_urls = Column(Text, nullable=True)  # JSON string for SQLite
    _image_hashes_json = Column("image_hashes", Text, nullable=True)  # JSON string for SQLite
    
    verification_status = Column(String(20), nullable=True, default='unverified')
    confidence_score = Column(Float, nullable=True)
    signals = Column(Text, nullable=True)  # JSON string for SQLite
    
    cluster_id = Column(String, ForeignKey('event_clusters.id'), nullable=True)
    
    admin_override = Column(Float, default=0)  # Boolean as 0/1
    admin_notes = Column(Text, nullable=True)
    admin_user_id = Column(String, nullable=True)
    
    user_id = Column(String, nullable=True)  # Added for pipeline tests
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)  # Added for pipeline tests
    reported_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    ingested_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    verified_at = Column(TIMESTAMP, nullable=True)
    
    def __init__(self, **kwargs):
        """Initialize model, defaulting reported_at to created_at if not explicitly set."""
        # If created_at is set but reported_at is not, copy created_at to reported_at
        if 'created_at' in kwargs and 'reported_at' not in kwargs:
            kwargs['reported_at'] = kwargs['created_at']
        super().__init__(**kwargs)
    
    @hybrid_property
    def image_hashes(self):
        """Get image_hashes as a list (deserialize from JSON)."""
        if self._image_hashes_json:
            try:
                return json.loads(self._image_hashes_json)
            except:
                return []
        return []
    
    @image_hashes.setter
    def image_hashes(self, value):
        """Set image_hashes (serialize to JSON)."""
        if value is not None:
            self._image_hashes_json = json.dumps(value)
        else:
            self._image_hashes_json = None
    
    @image_hashes.expression
    def image_hashes(cls):
        """SQL expression for image_hashes column."""
        return cls._image_hashes_json


class EventClusterTest(TestBase):
    """Simplified EventCluster model for testing (without PostGIS)."""
    
    __tablename__ = "event_clusters"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=True)
    canonical_text = Column(Text, nullable=True)
    centroid = Column(Text, nullable=True)  # Simplified location for SQLite (no Geography type)
    report_ids = Column(Text, nullable=True)  # JSON string for SQLite
    report_count = Column(Float, default=1)
    first_reported_at = Column(TIMESTAMP, nullable=True)
    last_reported_at = Column(TIMESTAMP, nullable=True)


class VerificationLogTest(TestBase):
    """Simplified VerificationLog model for testing."""
    
    __tablename__ = "verification_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String, ForeignKey('weather_reports.id'), nullable=False)
    verification_step = Column(String(100), nullable=False)
    result = Column(Text, nullable=True)  # JSON string for SQLite
    executed_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)


@pytest.fixture(scope="session", autouse=True)
def patch_models():
    """Patch the model imports in ML modules to use test models."""
    import app.ml.deduplicator as deduplicator_module
    import app.ml.image_hash as image_hash_module
    import app.ml.confidence as confidence_module
    import app.ml.location_verifier as location_verifier_module
    import app.ml.pipeline as pipeline_module
    import app.ml.verifier as verifier_module
    
    # Patch deduplicator
    deduplicator_module.WeatherReport = WeatherReportTest
    deduplicator_module.EventCluster = EventClusterTest
    deduplicator_module.VerificationLog = VerificationLogTest
    
    # Patch image_hash
    image_hash_module.WeatherReport = WeatherReportTest
    image_hash_module.VerificationLog = VerificationLogTest
    
    # Patch confidence
    confidence_module.WeatherReport = WeatherReportTest
    confidence_module.VerificationLog = VerificationLogTest
    
    # Patch location_verifier
    location_verifier_module.WeatherReport = WeatherReportTest
    
    # Patch pipeline
    pipeline_module.WeatherReport = WeatherReportTest
    pipeline_module.VerificationLog = VerificationLogTest
    
    # Patch verifier
    verifier_module.WeatherReport = WeatherReportTest
    verifier_module.VerificationLog = VerificationLogTest


@pytest_asyncio.fixture
async def db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)
    
    yield engine
    
    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


# Patch the ground_truth_check function to handle test models with lat/lon columns
import app.ml.verifier as verifier_module_patch

_original_ground_truth_check = verifier_module_patch.ground_truth_check

async def patched_ground_truth_check(report_id: str, db):
    """Patched ground_truth_check that handles test models with lat/lon columns."""
    from sqlalchemy import select
    
    # Get report
    result = await db.execute(
        select(WeatherReportTest).where(WeatherReportTest.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        from app.ml.verifier import GroundTruthVerificationResult
        return GroundTruthVerificationResult(
            plausible=False,
            confidence=0.0,
            error="Report not found",
            reasoning="Cannot verify non-existent report"
        )
    
    # Check if we have latitude/longitude
    if report.latitude is None or report.longitude is None:
        from app.ml.verifier import GroundTruthVerificationResult
        return GroundTruthVerificationResult(
            plausible=False,
            confidence=0.5,
            error="No location data",
            reasoning="Cannot verify report without location information"
        )
    
    # Perform verification using lat/lon directly
    from app.ml.verifier import WeatherVerifier
    verifier = WeatherVerifier()
    verification_result = await verifier.verify_report(
        event_type=report.event_type or "unknown",
        latitude=report.latitude,
        longitude=report.longitude,
        reported_at=report.created_at or report.reported_at
    )
    
    # Log verification step
    log_entry = VerificationLogTest(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps(verification_result.to_dict())
    )
    db.add(log_entry)
    
    try:
        await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to log verification: {e}")
        await db.rollback()
    
    return verification_result

verifier_module_patch.ground_truth_check = patched_ground_truth_check


# Mock Redis client for tests
@pytest.fixture(scope="session", autouse=True)
def mock_redis():
    """Mock Redis client to avoid connection errors in tests."""
    import app.core.redis_client as redis_module
    
    class MockRedis:
        async def connect(self):
            pass
        
        async def disconnect(self):
            pass
        
        async def ping(self):
            return True
        
        @property
        def redis(self):
            return self
    
    redis_module.redis_client = MockRedis()
    yield
    # No cleanup needed


# Patch WeatherReport in reports API to use test model
@pytest.fixture(scope="session", autouse=True)
def patch_api_models():
    """Patch WeatherReport in API module to use test model."""
    import app.api.reports as reports_module
    reports_module.WeatherReport = WeatherReportTest
    yield
