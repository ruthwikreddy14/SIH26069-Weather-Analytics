from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.redis_client import redis_client
from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify all services are operational.
    
    Checks:
    - FastAPI application is running
    - PostgreSQL database connection
    - PostGIS extension availability
    - Redis connection
    """
    
    # Check database connection and PostGIS
    db_status = "disconnected"
    postgis_version = None
    
    try:
        # Test basic database connection
        result = await db.execute(text("SELECT 1"))
        result.fetchone()
        
        # Check PostGIS extension
        postgis_result = await db.execute(text("SELECT PostGIS_version()"))
        postgis_row = postgis_result.fetchone()
        if postgis_row:
            postgis_version = postgis_row[0]
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Check Redis connection
    redis_status = "disconnected"
    try:
        if redis_client.redis:
            await redis_client.redis.ping()
            redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    # Determine overall status
    overall_status = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"
    
    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
        details={
            "postgis_version": postgis_version,
            "debug_mode": settings.DEBUG
        }
    )


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }
