"""
Alerts API

Provides endpoints for weather alert management and retrieval.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.services.alerts import get_alert_service
from app.api.risk import assess_risks

router = APIRouter()
logger = logging.getLogger(__name__)


class AlertUpdateRequest(BaseModel):
    """Request model for updating alert status"""
    status: Optional[str] = None
    response_status: Optional[str] = None
    response_notes: Optional[str] = None


@router.get("/active")
async def get_active_alerts(db: AsyncSession = Depends(get_db)):
    """
    Get all active weather alerts.
    
    Returns alerts sorted by risk score (highest first).
    Only includes alerts for HIGH and CRITICAL risk events.
    
    Returns:
        List of active alerts with full details
    """
    logger.info("Fetching active alerts")
    
    try:
        # Get risk assessments
        risk_response = await assess_risks(None, 200, db)
        assessments = risk_response.get('assessments', [])
        
        # Generate/update alerts from assessments
        alert_service = get_alert_service()
        alert_service.generate_alerts_from_assessments(assessments)
        
        # Get active alerts
        active_alerts = alert_service.get_active_alerts()
        
        # Convert to response format
        alerts_response = []
        for alert in active_alerts:
            alerts_response.append({
                'alert_id': alert.alert_id,
                'event_id': alert.event_id,
                'event_type': alert.event_type,
                'risk_level': alert.risk_level,
                'risk_score': alert.risk_score,
                'severity': alert.severity,
                'location': {
                    'lat': alert.center_lat,
                    'lon': alert.center_lon,
                    'description': alert.location_description
                },
                'affected_radius_km': alert.affected_radius_km,
                'report_count': alert.report_count,
                'verified_count': alert.verified_count,
                'confidence': alert.confidence,
                'created_at': alert.created_at.isoformat(),
                'expires_at': alert.expires_at.isoformat() if alert.expires_at else None,
                'status': alert.status,
                'alert_message': alert.alert_message,
                'recommended_action': alert.recommended_action,
                'response_status': alert.response_status,
                'response_notes': alert.response_notes,
                'updated_at': alert.updated_at.isoformat()
            })
        
        # Count by severity
        emergency_count = sum(1 for a in active_alerts if a.severity == 'EMERGENCY')
        warning_count = sum(1 for a in active_alerts if a.severity == 'WARNING')
        
        logger.info(f"Found {len(active_alerts)} active alerts "
                   f"({emergency_count} emergency, {warning_count} warning)")
        
        return {
            "alerts": alerts_response,
            "total_alerts": len(alerts_response),
            "emergency_count": emergency_count,
            "warning_count": warning_count
        }
        
    except Exception as e:
        logger.error(f"Error fetching active alerts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


@router.get("/{alert_id}")
async def get_alert_details(alert_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed information for a specific alert.
    
    Args:
        alert_id: Alert UUID
        db: Database session
        
    Returns:
        Detailed alert information including event details
    """
    logger.info(f"Fetching alert details: {alert_id}")
    
    try:
        alert_service = get_alert_service()
        alert = alert_service.get_alert_by_id(alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        # Get the associated risk assessment for full details
        from app.api.risk import assess_event_risk
        try:
            risk_assessment = await assess_event_risk(alert.event_id, db)
        except:
            risk_assessment = None
        
        return {
            'alert_id': alert.alert_id,
            'event_id': alert.event_id,
            'event_type': alert.event_type,
            'risk_level': alert.risk_level,
            'risk_score': alert.risk_score,
            'severity': alert.severity,
            'location': {
                'lat': alert.center_lat,
                'lon': alert.center_lon,
                'description': alert.location_description
            },
            'affected_radius_km': alert.affected_radius_km,
            'report_count': alert.report_count,
            'verified_count': alert.verified_count,
            'confidence': alert.confidence,
            'created_at': alert.created_at.isoformat(),
            'expires_at': alert.expires_at.isoformat() if alert.expires_at else None,
            'status': alert.status,
            'alert_message': alert.alert_message,
            'recommended_action': alert.recommended_action,
            'response_status': alert.response_status,
            'response_notes': alert.response_notes,
            'updated_at': alert.updated_at.isoformat(),
            'risk_assessment': risk_assessment
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching alert: {str(e)}")


@router.patch("/{alert_id}")
async def update_alert(alert_id: str, update: AlertUpdateRequest):
    """
    Update alert status and response information.
    
    Allows authorities to update:
    - Alert status (ACTIVE, MONITORING, RESOLVED)
    - Response status (PENDING, MONITORING, INVESTIGATING, RESPONSE_INITIATED, RESOLVED)
    - Response notes
    
    Args:
        alert_id: Alert UUID
        update: Update request with new values
        
    Returns:
        Updated alert information
    """
    logger.info(f"Updating alert {alert_id}: status={update.status}, "
               f"response={update.response_status}")
    
    try:
        alert_service = get_alert_service()
        
        updated_alert = alert_service.update_alert_status(
            alert_id,
            update.status or 'ACTIVE',
            update.response_status,
            update.response_notes
        )
        
        if not updated_alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        return {
            'alert_id': updated_alert.alert_id,
            'status': updated_alert.status,
            'response_status': updated_alert.response_status,
            'response_notes': updated_alert.response_notes,
            'updated_at': updated_alert.updated_at.isoformat(),
            'message': 'Alert updated successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating alert: {str(e)}")


@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, notes: Optional[str] = None):
    """
    Mark alert as resolved.
    
    Args:
        alert_id: Alert UUID
        notes: Optional resolution notes
        
    Returns:
        Resolved alert information
    """
    logger.info(f"Resolving alert {alert_id}")
    
    try:
        alert_service = get_alert_service()
        resolved_alert = alert_service.resolve_alert(alert_id, notes)
        
        if not resolved_alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        return {
            'alert_id': resolved_alert.alert_id,
            'status': resolved_alert.status,
            'response_status': resolved_alert.response_status,
            'response_notes': resolved_alert.response_notes,
            'updated_at': resolved_alert.updated_at.isoformat(),
            'message': 'Alert resolved successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error resolving alert: {str(e)}")


@router.get("/summary/stats")
async def get_alert_stats(db: AsyncSession = Depends(get_db)):
    """
    Get alert statistics summary.
    
    Returns counts and metrics for active alerts.
    """
    try:
        # Get active alerts
        alerts_response = await get_active_alerts(db)
        
        alerts = alerts_response.get('alerts', [])
        
        # Calculate statistics
        total_active = len(alerts)
        emergency_count = alerts_response.get('emergency_count', 0)
        warning_count = alerts_response.get('warning_count', 0)
        
        # Response status breakdown
        pending_count = sum(1 for a in alerts if a.get('response_status') == 'PENDING')
        monitoring_count = sum(1 for a in alerts if a.get('response_status') == 'MONITORING')
        investigating_count = sum(1 for a in alerts if a.get('response_status') == 'INVESTIGATING')
        responding_count = sum(1 for a in alerts if a.get('response_status') == 'RESPONSE_INITIATED')
        
        return {
            'total_active_alerts': total_active,
            'emergency_alerts': emergency_count,
            'warning_alerts': warning_count,
            'response_breakdown': {
                'pending': pending_count,
                'monitoring': monitoring_count,
                'investigating': investigating_count,
                'responding': responding_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting alert stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")
