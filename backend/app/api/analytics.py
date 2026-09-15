"""
Analytics API endpoints for dashboard statistics.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.database import get_db
from app.models.weather_report import WeatherReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class DashboardStats(BaseModel):
    """Dashboard statistics response schema."""
    total_reports: int
    verified_count: int
    fake_count: int
    disputed_count: int
    verified_percentage: float


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """
    Get dashboard statistics including total reports and counts by verification status.
    
    Returns:
    - total_reports: Total number of reports in the system
    - verified_count: Number of verified reports (confidence > 0.7)
    - fake_count: Number of fake reports (confidence < 0.4)
    - disputed_count: Number of disputed reports (0.4 <= confidence <= 0.7)
    - verified_percentage: Percentage of verified reports
    """
    logger.info("Fetching dashboard statistics")
    
    try:
        # Total reports count
        total_query = select(func.count(WeatherReport.id))
        total_result = await db.execute(total_query)
        total_reports = total_result.scalar() or 0
        
        # Verified count (verification_status = 'verified')
        verified_query = select(func.count(WeatherReport.id)).where(
            WeatherReport.verification_status == 'verified'
        )
        verified_result = await db.execute(verified_query)
        verified_count = verified_result.scalar() or 0
        
        # Fake count (verification_status = 'fake')
        fake_query = select(func.count(WeatherReport.id)).where(
            WeatherReport.verification_status == 'fake'
        )
        fake_result = await db.execute(fake_query)
        fake_count = fake_result.scalar() or 0
        
        # Disputed count (verification_status = 'disputed')
        disputed_query = select(func.count(WeatherReport.id)).where(
            WeatherReport.verification_status == 'disputed'
        )
        disputed_result = await db.execute(disputed_query)
        disputed_count = disputed_result.scalar() or 0
        
        # Calculate verified percentage
        verified_percentage = (verified_count / total_reports * 100) if total_reports > 0 else 0.0
        
        stats = DashboardStats(
            total_reports=total_reports,
            verified_count=verified_count,
            fake_count=fake_count,
            disputed_count=disputed_count,
            verified_percentage=verified_percentage
        )
        
        logger.info(f"Dashboard stats: {stats.model_dump()}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to fetch dashboard stats: {str(e)}")
        # Return zero stats if query fails
        return DashboardStats(
            total_reports=0,
            verified_count=0,
            fake_count=0,
            disputed_count=0,
            verified_percentage=0.0
        )
