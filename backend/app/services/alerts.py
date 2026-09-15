"""
Early Warning & Alert System

Generates alerts for HIGH and CRITICAL risk weather events.
Manages alert lifecycle and provides alert information to authorities.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class WeatherAlert:
    """Weather alert for high-risk events"""
    alert_id: str
    event_id: str
    event_type: str
    risk_level: str  # HIGH or CRITICAL
    risk_score: float
    severity: str  # WARNING or EMERGENCY
    
    # Location information
    center_lat: float
    center_lon: float
    affected_radius_km: float
    location_description: str
    
    # Event details
    report_count: int
    verified_count: int
    confidence: float
    
    # Alert metadata
    created_at: datetime
    expires_at: Optional[datetime]
    status: str  # ACTIVE, MONITORING, RESOLVED
    
    # Messages
    alert_message: str
    recommended_action: str
    
    # Response tracking
    response_status: str  # PENDING, MONITORING, INVESTIGATING, RESPONSE_INITIATED, RESOLVED
    response_notes: Optional[str]
    updated_at: datetime


class AlertGenerationService:
    """
    Service for generating and managing weather alerts.
    
    Alerts are generated when:
    - Risk level is HIGH (61-85)
    - Risk level is CRITICAL (86-100)
    
    Alert severities:
    - WARNING: HIGH risk events
    - EMERGENCY: CRITICAL risk events
    """
    
    def __init__(self):
        # In-memory storage for MVP (should be database in production)
        self._active_alerts: Dict[str, WeatherAlert] = {}
        self._alert_history: List[WeatherAlert] = []
        logger.info("Alert Generation Service initialized")
    
    def generate_alerts_from_assessments(self, risk_assessments: List[Dict]) -> List[WeatherAlert]:
        """
        Generate alerts from risk assessments.
        
        Args:
            risk_assessments: List of risk assessment dictionaries
            
        Returns:
            List of newly created alerts
        """
        new_alerts = []
        
        for assessment in risk_assessments:
            risk_level = assessment.get('risk_level')
            
            # Only generate alerts for HIGH and CRITICAL risks
            if risk_level not in ['HIGH', 'CRITICAL']:
                continue
            
            event_id = assessment.get('event_id')
            
            # Check if alert already exists for this event
            if self._alert_exists_for_event(event_id):
                # Update existing alert
                alert = self._update_existing_alert(assessment)
                if alert:
                    logger.info(f"Updated existing alert {alert.alert_id} for event {event_id}")
            else:
                # Create new alert
                alert = self._create_alert(assessment)
                self._active_alerts[alert.alert_id] = alert
                self._alert_history.append(alert)
                new_alerts.append(alert)
                logger.info(f"Created new alert {alert.alert_id} for event {event_id} ({risk_level} risk)")
        
        return new_alerts
    
    def get_active_alerts(self) -> List[WeatherAlert]:
        """Get all active alerts sorted by risk score (highest first)"""
        active = [alert for alert in self._active_alerts.values() if alert.status == 'ACTIVE']
        active.sort(key=lambda a: a.risk_score, reverse=True)
        return active
    
    def get_alert_by_id(self, alert_id: str) -> Optional[WeatherAlert]:
        """Get specific alert by ID"""
        return self._active_alerts.get(alert_id)
    
    def get_alert_by_event_id(self, event_id: str) -> Optional[WeatherAlert]:
        """Get alert for specific event"""
        for alert in self._active_alerts.values():
            if alert.event_id == event_id:
                return alert
        return None
    
    def update_alert_status(self, alert_id: str, status: str, 
                           response_status: Optional[str] = None,
                           response_notes: Optional[str] = None) -> Optional[WeatherAlert]:
        """Update alert status and response information"""
        alert = self._active_alerts.get(alert_id)
        
        if not alert:
            logger.warning(f"Alert {alert_id} not found")
            return None
        
        alert.status = status
        if response_status:
            alert.response_status = response_status
        if response_notes:
            alert.response_notes = response_notes
        alert.updated_at = datetime.utcnow()
        
        logger.info(f"Updated alert {alert_id}: status={status}, response={response_status}")
        
        return alert
    
    def resolve_alert(self, alert_id: str, notes: Optional[str] = None) -> Optional[WeatherAlert]:
        """Mark alert as resolved"""
        return self.update_alert_status(alert_id, 'RESOLVED', 'RESOLVED', notes)
    
    def _alert_exists_for_event(self, event_id: str) -> bool:
        """Check if active alert exists for event"""
        return any(
            alert.event_id == event_id and alert.status == 'ACTIVE'
            for alert in self._active_alerts.values()
        )
    
    def _update_existing_alert(self, assessment: Dict) -> Optional[WeatherAlert]:
        """Update existing alert with new assessment"""
        event_id = assessment.get('event_id')
        alert = self.get_alert_by_event_id(event_id)
        
        if not alert:
            return None
        
        # Update alert with new information
        alert.risk_score = assessment.get('risk_score', alert.risk_score)
        alert.risk_level = assessment.get('risk_level', alert.risk_level)
        alert.severity = 'EMERGENCY' if alert.risk_level == 'CRITICAL' else 'WARNING'
        alert.confidence = assessment.get('confidence', alert.confidence)
        alert.updated_at = datetime.utcnow()
        
        # Update event details if available
        event_details = assessment.get('event_details', {})
        if event_details:
            alert.report_count = event_details.get('report_count', alert.report_count)
            verification = event_details.get('verification_summary', {})
            alert.verified_count = verification.get('verified', alert.verified_count)
        
        return alert
    
    def _create_alert(self, assessment: Dict) -> WeatherAlert:
        """Create new alert from risk assessment"""
        event_id = assessment.get('event_id')
        event_type = assessment.get('event_type')
        risk_level = assessment.get('risk_level')
        risk_score = assessment.get('risk_score')
        
        # Determine severity
        severity = 'EMERGENCY' if risk_level == 'CRITICAL' else 'WARNING'
        
        # Extract event details
        event_details = assessment.get('event_details', {})
        center = event_details.get('center', {})
        center_lat = center.get('lat', 0.0)
        center_lon = center.get('lon', 0.0)
        affected_radius_km = event_details.get('affected_radius_km', 0.0)
        report_count = event_details.get('report_count', 0)
        verification = event_details.get('verification_summary', {})
        verified_count = verification.get('verified', 0)
        confidence = assessment.get('confidence', 0.0)
        
        # Generate location description
        location_description = f"{center_lat:.3f}°N, {center_lon:.3f}°E"
        
        # Generate alert message
        alert_message = self._generate_alert_message(
            severity, event_type, report_count, verified_count,
            confidence, affected_radius_km, location_description
        )
        
        # Get recommended action
        recommended_action = assessment.get('recommended_action', 'Monitor situation closely')
        
        alert = WeatherAlert(
            alert_id=str(uuid.uuid4()),
            event_id=event_id,
            event_type=event_type,
            risk_level=risk_level,
            risk_score=risk_score,
            severity=severity,
            center_lat=center_lat,
            center_lon=center_lon,
            affected_radius_km=affected_radius_km,
            location_description=location_description,
            report_count=report_count,
            verified_count=verified_count,
            confidence=confidence,
            created_at=datetime.utcnow(),
            expires_at=None,  # Could set expiration based on event type
            status='ACTIVE',
            alert_message=alert_message,
            recommended_action=recommended_action,
            response_status='PENDING',
            response_notes=None,
            updated_at=datetime.utcnow()
        )
        
        return alert
    
    def _generate_alert_message(self, severity: str, event_type: str,
                               report_count: int, verified_count: int,
                               confidence: float, radius: float,
                               location: str) -> str:
        """Generate alert message text"""
        if severity == 'EMERGENCY':
            prefix = "🚨 CRITICAL WEATHER ALERT"
            urgency = "IMMEDIATE ATTENTION REQUIRED"
        else:
            prefix = "⚠️ HIGH RISK WEATHER ALERT"
            urgency = "MONITORING RECOMMENDED"
        
        message = f"{prefix}\n\n"
        message += f"{urgency}\n\n"
        message += f"{event_type.title()} detected\n"
        message += f"Location: {location}\n"
        message += f"{report_count} reports detected ({verified_count} verified)\n"
        message += f"Confidence: {confidence * 100:.0f}%\n"
        message += f"Affected radius: {radius:.1f} km\n\n"
        message += "This is a platform-generated AI risk alert based on citizen reports and verification algorithms."
        
        return message


# Singleton instance
_alert_service: Optional[AlertGenerationService] = None


def get_alert_service() -> AlertGenerationService:
    """Get singleton instance of alert service"""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertGenerationService()
    return _alert_service
