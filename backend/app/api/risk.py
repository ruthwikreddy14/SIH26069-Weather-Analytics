"""
Risk Detection API

Provides endpoints for weather event risk assessment.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.api.events import get_event_clusters
from app.ml.risk_detection import get_risk_detection_engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/assess")
async def assess_risks(
    event_type: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Assess risks for detected weather events.
    
    Returns risk assessments for all detected event clusters including:
    - Risk score (0-100)
    - Risk level (LOW, MODERATE, HIGH, CRITICAL)
    - Contributing factors
    - Explanation
    - Recommended action
    
    Args:
        event_type: Optional filter by event type
        limit: Maximum number of events to assess
        db: Database session
    
    Returns:
        List of risk assessments
    """
    logger.info(f"Risk assessment request: event_type={event_type}, limit={limit}")
    
    try:
        # Get event clusters using existing clustering endpoint logic
        clusters_response = await get_event_clusters(event_type, limit, db)
        
        clusters = clusters_response.get('clusters', [])
        
        if not clusters:
            return {
                "assessments": [],
                "total_assessments": 0,
                "high_risk_count": 0,
                "critical_risk_count": 0,
                "message": "No events available for risk assessment"
            }
        
        # Assess risk for each cluster
        risk_engine = get_risk_detection_engine()
        assessments = []
        high_risk_count = 0
        critical_risk_count = 0
        
        for cluster in clusters:
            try:
                assessment = risk_engine.assess_risk(cluster)
                
                # Count high-risk events
                if assessment.risk_level == 'HIGH':
                    high_risk_count += 1
                elif assessment.risk_level == 'CRITICAL':
                    critical_risk_count += 1
                
                # Convert to response format
                assessment_dict = {
                    'event_id': assessment.event_id,
                    'event_type': assessment.event_type,
                    'risk_score': assessment.risk_score,
                    'risk_level': assessment.risk_level,
                    'factors': assessment.factors,
                    'explanation': assessment.explanation,
                    'recommended_action': assessment.recommended_action,
                    'confidence': assessment.confidence,
                    'assessed_at': assessment.assessed_at.isoformat(),
                    'insufficient_data': assessment.insufficient_data,
                    # Include event details for context
                    'event_details': {
                        'center': cluster.get('center'),
                        'report_count': cluster.get('report_count'),
                        'affected_radius_km': cluster.get('affected_radius_km'),
                        'time_range': cluster.get('time_range'),
                        'verification_summary': cluster.get('verification_summary')
                    }
                }
                
                assessments.append(assessment_dict)
                
            except Exception as e:
                logger.error(f"Failed to assess risk for event {cluster.get('event_id')}: {e}")
                continue
        
        # Sort by risk score (highest first)
        assessments.sort(key=lambda x: x['risk_score'], reverse=True)
        
        logger.info(f"Risk assessment complete: {len(assessments)} events assessed, "
                   f"{critical_risk_count} critical, {high_risk_count} high risk")
        
        return {
            "assessments": assessments,
            "total_assessments": len(assessments),
            "high_risk_count": high_risk_count,
            "critical_risk_count": critical_risk_count,
            "clustering_params": clusters_response.get('clustering_params')
        }
        
    except Exception as e:
        logger.error(f"Error in risk assessment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error assessing risks: {str(e)}")


@router.get("/assess/{event_id}")
async def assess_event_risk(
    event_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Assess risk for a specific weather event.
    
    Args:
        event_id: Event cluster ID
        db: Database session
    
    Returns:
        Risk assessment for the specified event
    """
    logger.info(f"Risk assessment request for event: {event_id}")
    
    try:
        # Get all clusters and find the matching one
        clusters_response = await get_event_clusters(None, 1000, db)
        clusters = clusters_response.get('clusters', [])
        
        # Find the specific event
        event_cluster = None
        for cluster in clusters:
            if cluster.get('event_id') == event_id:
                event_cluster = cluster
                break
        
        if not event_cluster:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        
        # Assess risk
        risk_engine = get_risk_detection_engine()
        assessment = risk_engine.assess_risk(event_cluster)
        
        return {
            'event_id': assessment.event_id,
            'event_type': assessment.event_type,
            'risk_score': assessment.risk_score,
            'risk_level': assessment.risk_level,
            'factors': assessment.factors,
            'explanation': assessment.explanation,
            'recommended_action': assessment.recommended_action,
            'confidence': assessment.confidence,
            'assessed_at': assessment.assessed_at.isoformat(),
            'insufficient_data': assessment.insufficient_data,
            'event_details': {
                'center': event_cluster.get('center'),
                'report_count': event_cluster.get('report_count'),
                'affected_radius_km': event_cluster.get('affected_radius_km'),
                'time_range': event_cluster.get('time_range'),
                'verification_summary': event_cluster.get('verification_summary'),
                'report_ids': event_cluster.get('report_ids')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assessing risk for event {event_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error assessing risk: {str(e)}")
