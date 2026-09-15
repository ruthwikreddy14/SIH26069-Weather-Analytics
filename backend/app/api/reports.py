"""
Reports API endpoints for weather report submission and retrieval.
"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import List, Optional
from datetime import datetime
from geoalchemy2.functions import ST_X, ST_Y

from app.core.database import get_db
from app.models.weather_report import WeatherReport
from app.schemas.report import (
    ReportCreate,
    ReportSubmitResponse,
    ReportResponse,
    ReportDetail,
    ReportListResponse,
    LocationInfo
)
from app.ml.pipeline import verify_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/submit", response_model=ReportSubmitResponse, status_code=201)
async def submit_report(
    report_data: ReportCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a new weather report from citizen form.
    
    This endpoint:
    1. Validates the input data
    2. Creates a new report in the database with status=pending
    3. Optionally triggers async verification (currently synchronous for demo)
    4. Returns the report ID
    
    In production, this would:
    - Upload media files to MinIO
    - Publish to Kafka for async processing
    - Return immediately without waiting for verification
    """
    logger.info(f"Received report submission: {report_data.event_type} in {report_data.city}")
    
    try:
        # Create WeatherReport instance
        new_report = WeatherReport(
            source_type="citizen_form",
            raw_text=report_data.description,
            event_type=report_data.event_type,
            city=report_data.city,
            state=report_data.state,
            verification_status="unverified"
        )
        
        # Set GPS location if provided
        if report_data.gps:
            # Create PostGIS POINT from GPS coordinates
            # Format: ST_GeogFromText('POINT(lon lat)')
            from geoalchemy2.elements import WKTElement
            point = WKTElement(f'POINT({report_data.gps.lon} {report_data.gps.lat})', srid=4326)
            new_report.location = point
        
        # Handle media files (placeholder for future MinIO integration)
        if report_data.media_files:
            # In production: upload to MinIO and store URLs
            # For now, just note that media was provided
            logger.info(f"Report has {len(report_data.media_files)} media files (MinIO integration pending)")
        
        # Save to database
        db.add(new_report)
        await db.flush()  # Get the ID without committing
        
        report_id = new_report.id
        
        # Commit the report
        await db.commit()
        
        logger.info(f"Report {report_id} created successfully")
        
        # Trigger verification pipeline (async in production via Celery/Kafka)
        # For MVP demo: run verification synchronously if not in test mode
        # In tests, skip verification to avoid external dependencies
        import os
        if not os.getenv("PYTEST_CURRENT_TEST"):
            try:
                logger.info(f"Starting verification for report {report_id}")
                verification_result = await verify_report(str(report_id), db)
                logger.info(
                    f"Verification complete: confidence={verification_result.confidence_score:.2f}, "
                    f"status={verification_result.verification_status}"
                )
            except Exception as e:
                logger.error(f"Verification failed for report {report_id}: {str(e)}")
                # Don't fail the submission if verification fails
        
        return ReportSubmitResponse(
            report_id=report_id,
            status="pending",
            message="Report submitted successfully. Verification in progress."
        )
    
    except Exception as e:
        logger.error(f"Failed to submit report: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit report: {str(e)}")


@router.get("", response_model=ReportListResponse)
async def get_reports(
    date_from: Optional[str] = Query(None, description="Filter reports from this date (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter reports until this date (ISO format)"),
    event_type: Optional[str] = Query(None, description="Comma-separated event types (e.g., flooding,rainfall)"),
    state: Optional[str] = Query(None, description="Filter by state"),
    status: Optional[str] = Query(None, description="Comma-separated verification statuses (e.g., verified,disputed)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a list of weather reports with optional filters and pagination.
    
    Supports filtering by:
    - Date range (date_from, date_to)
    - Event type (rainfall, flooding, thunderstorm, etc.)
    - State
    - Verification status (verified, disputed, fake, unverified)
    
    Returns paginated results with total count.
    """
    logger.info(f"Fetching reports: filters=(date_from={date_from}, date_to={date_to}, event_type={event_type}, state={state}, status={status})")
    
    try:
        # Parse date parameters
        parsed_date_from = None
        parsed_date_to = None
        if date_from:
            try:
                # Handle URL encoding where + becomes space
                date_from_fixed = date_from.replace(' ', '+')
                parsed_date_from = datetime.fromisoformat(date_from_fixed)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date_from format: {str(e)}")
        if date_to:
            try:
                # Handle URL encoding where + becomes space
                date_to_fixed = date_to.replace(' ', '+')
                parsed_date_to = datetime.fromisoformat(date_to_fixed)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date_to format: {str(e)}")
        
        # Build query with filters
        query = select(WeatherReport)
        conditions = []
        
        # Date range filter
        if parsed_date_from:
            conditions.append(WeatherReport.reported_at >= parsed_date_from)
        if parsed_date_to:
            conditions.append(WeatherReport.reported_at <= parsed_date_to)
        
        # Event type filter (comma-separated list)
        if event_type:
            event_types = [et.strip() for et in event_type.split(",")]
            conditions.append(WeatherReport.event_type.in_(event_types))
        
        # State filter
        if state:
            conditions.append(WeatherReport.state == state)
        
        # Verification status filter (comma-separated list)
        if status:
            statuses = [s.strip() for s in status.split(",")]
            conditions.append(WeatherReport.verification_status.in_(statuses))
        
        # Apply all conditions
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by most recent first
        query = query.order_by(WeatherReport.reported_at.desc())
        
        # Get total count
        count_query = select(func.count()).select_from(WeatherReport)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await db.execute(query)
        reports = result.scalars().all()
        
        # Convert to response format
        report_responses = []
        for report in reports:
            # Extract location info including GPS coordinates
            location_info = None
            lat = None
            lon = None
            
            # Extract lat/lon from PostGIS Geography point
            if report.location:
                try:
                    # Parse WKB to get coordinates
                    from geoalchemy2.shape import to_shape
                    point = to_shape(report.location)
                    lon = point.x
                    lat = point.y
                except Exception as e:
                    logger.warning(f"Failed to extract GPS from report {report.id}: {e}")
            
            # Create location info if we have any location data
            if lat or lon or report.city or report.state:
                location_info = LocationInfo(
                    lat=lat,
                    lon=lon,
                    city=report.city,
                    state=report.state,
                    location_source=report.location_source,
                    location_confidence=report.location_confidence
                )
            
            # Parse signals if stored as JSON string (SQLite Text vs PostgreSQL JSONB)
            signals_data = report.signals
            if isinstance(signals_data, str):
                try:
                    signals_data = json.loads(signals_data)
                except (json.JSONDecodeError, TypeError):
                    signals_data = None
            
            report_responses.append(ReportResponse(
                id=str(report.id),  # Convert UUID to string
                event_type=report.event_type,
                description=report.raw_text,
                location=location_info,
                verification_status=report.verification_status,
                confidence_score=report.confidence_score,
                reported_at=report.reported_at,
                media_urls=report.media_urls,
                signals=signals_data
            ))
        
        logger.info(f"Found {len(report_responses)} reports (total: {total})")
        
        return ReportListResponse(
            reports=report_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    
    except Exception as e:
        logger.error(f"Failed to fetch reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report_by_id(
    report_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information for a specific weather report by ID.
    
    Returns:
    - All report fields
    - Complete verification results and signals
    - Location details
    - Admin notes if any
    """
    logger.info(f"Fetching report details for {report_id}")
    
    try:
        # Query for the specific report
        query = select(WeatherReport).where(WeatherReport.id == report_id)
        result = await db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        
        # Extract location info including GPS coordinates
        location_info = None
        lat = None
        lon = None
        
        # Extract lat/lon from PostGIS Geography point
        if report.location:
            try:
                # Parse WKB to get coordinates
                from geoalchemy2.shape import to_shape
                point = to_shape(report.location)
                lon = point.x
                lat = point.y
            except Exception as e:
                logger.warning(f"Failed to extract GPS from report {report.id}: {e}")
        
        # Create location info if we have any location data
        if lat or lon or report.city or report.state:
            location_info = LocationInfo(
                lat=lat,
                lon=lon,
                city=report.city,
                state=report.state,
                location_source=report.location_source,
                location_confidence=report.location_confidence
            )
        
        # Parse signals if stored as JSON string (SQLite Text vs PostgreSQL JSONB)
        signals_data = report.signals
        if isinstance(signals_data, str):
            try:
                signals_data = json.loads(signals_data)
            except (json.JSONDecodeError, TypeError):
                signals_data = None
        
        return ReportDetail(
            id=str(report.id),  # Convert UUID to string
            source_type=report.source_type,
            event_type=report.event_type,
            description=report.raw_text,
            location=location_info,
            city=report.city,
            state=report.state,
            verification_status=report.verification_status,
            confidence_score=report.confidence_score,
            signals=signals_data,
            cluster_id=str(report.cluster_id) if report.cluster_id else None,  # Convert UUID to string
            admin_override=report.admin_override,
            admin_notes=report.admin_notes,
            reported_at=report.reported_at,
            ingested_at=report.ingested_at,
            verified_at=report.verified_at,
            media_urls=report.media_urls
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch report {report_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {str(e)}")
