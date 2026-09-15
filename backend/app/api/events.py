"""
Weather Events API

Provides endpoints for retrieving clustered weather events.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.weather_report import WeatherReport
from app.ml.event_clustering import get_clustering_service, WeatherEventCluster

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/clusters")
async def get_event_clusters(
    event_type: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get clustered weather events.
    
    Clusters are formed by grouping reports based on:
    - Geographic proximity (50km radius)
    - Same event type
    - Temporal proximity (24 hour window)
    - Minimum 2 reports per cluster
    
    Args:
        event_type: Optional filter by event type
        limit: Maximum number of reports to consider (default 100)
        db: Database session
    
    Returns:
        List of weather event clusters with statistics
    """
    logger.info(f"Event clustering request: event_type={event_type}, limit={limit}")
    
    try:
        # Build query for reports
        query = select(WeatherReport)
        
        if event_type:
            query = query.where(WeatherReport.event_type == event_type)
        
        # Order by most recent and limit
        query = query.order_by(WeatherReport.reported_at.desc()).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        reports_db = result.scalars().all()
        
        logger.info(f"Found {len(reports_db)} reports in database")
        
        if not reports_db:
            return {
                "clusters": [],
                "total_clusters": 0,
                "total_reports_analyzed": 0,
                "message": "No reports available for clustering"
            }
        
        # Convert SQLAlchemy models to dictionaries
        reports = []
        for report in reports_db:
            # Extract lat/lon from PostGIS geometry using the same method as reports API
            lat, lon = None, None
            if report.location:
                try:
                    from geoalchemy2.shape import to_shape
                    point = to_shape(report.location)
                    lon = point.x
                    lat = point.y
                except Exception as e:
                    logger.error(f"Error extracting coordinates from report {report.id}: {e}")
                    continue
            
            if not lat or not lon:
                logger.debug(f"Report {report.id} has no valid GPS coordinates")
                continue
            
            reports.append({
                'id': str(report.id),
                'event_type': report.event_type,
                'location': {'lat': lat, 'lon': lon},
                'reported_at': report.reported_at,
                'verification_status': report.verification_status,
                'confidence_score': report.confidence_score,
                'description': report.raw_text  # Use raw_text field from the model
            })
        
        # Return empty result if no valid reports with coordinates
        if not reports:
            logger.info(f"No reports with valid GPS coordinates. Total reports queried: {len(reports_db)}")
            return {
                "clusters": [],
                "total_clusters": 0,
                "total_reports_analyzed": len(reports_db),
                "message": "Insufficient reports with valid GPS coordinates for clustering"
            }
        
        logger.info(f"Clustering {len(reports)} valid reports")
        
        # Run clustering algorithm
        clustering_service = get_clustering_service()
        clusters = clustering_service.cluster_reports(reports)
        
        logger.info(f"Formed {len(clusters)} clusters from {len(reports)} reports")
        
        # Convert clusters to response format
        cluster_responses = []
        for cluster in clusters:
            cluster_responses.append({
                'event_id': cluster.event_id,
                'event_type': cluster.event_type,
                'center': {
                    'lat': cluster.center_lat,
                    'lon': cluster.center_lon
                },
                'report_count': cluster.report_count,
                'report_ids': cluster.report_ids,
                'time_range': {
                    'start': cluster.start_time.isoformat(),
                    'end': cluster.end_time.isoformat()
                },
                'affected_radius_km': cluster.affected_radius_km,
                'avg_confidence_score': cluster.avg_confidence_score,
                'verification_summary': {
                    'verified': cluster.verified_count,
                    'disputed': cluster.disputed_count,
                    'fake': cluster.fake_count,
                    'unverified': cluster.unverified_count,
                    'dominant_status': cluster.dominant_status
                }
            })
        
        # Determine appropriate message
        if len(cluster_responses) == 0:
            message = f"Analyzed {len(reports)} reports - no significant weather events detected yet"
        else:
            message = None
        
        result = {
            "clusters": cluster_responses,
            "total_clusters": len(cluster_responses),
            "total_reports_analyzed": len(reports),
            "clustering_params": {
                "max_distance_km": clustering_service.max_distance_km,
                "max_time_window_hours": clustering_service.max_time_window_hours,
                "min_cluster_size": clustering_service.min_cluster_size
            }
        }
        
        if message:
            result["message"] = message
            
        return result
    
    except Exception as e:
        # Log the error but return empty result instead of failing
        logger.error(f"Error in event clustering: {str(e)}", exc_info=True)
        
        # Return empty result gracefully
        return {
            "clusters": [],
            "total_clusters": 0,
            "total_reports_analyzed": 0,
            "message": f"Unable to cluster events at this time"
        }
