"""
AI Weather Risk Detection Engine

Evaluates weather events/clusters to determine risk levels based on:
- Event type severity
- Number and quality of reports
- Verification confidence
- Geographic spread
- Ground truth confirmation

Risk levels: LOW, MODERATE, HIGH, CRITICAL
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# Event type severity weights (0.0 to 1.0)
EVENT_SEVERITY_WEIGHTS = {
    'flooding': 1.0,        # Most severe
    'thunderstorm': 0.9,
    'dust_storm': 0.8,
    'strong_wind': 0.7,
    'heatwave': 0.7,
    'rainfall': 0.6,
    'fog': 0.4,            # Least severe
}


@dataclass
class RiskFactor:
    """Individual risk factor contributing to overall risk"""
    name: str
    value: float  # 0.0 to 1.0
    weight: float  # Importance weight
    description: str
    met: bool  # Whether this factor contributes to risk


@dataclass
class RiskAssessment:
    """Complete risk assessment for a weather event"""
    event_id: str
    event_type: str
    risk_score: float  # 0-100
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    factors: List[Dict]
    explanation: str
    recommended_action: str
    confidence: float  # Overall confidence in the assessment
    assessed_at: datetime
    insufficient_data: bool = False


class WeatherRiskDetectionEngine:
    """
    AI-powered risk detection engine for weather events.
    
    Risk Score Calculation (0-100):
    1. Event Severity (25%): Based on event type
    2. Report Quality (25%): Number and verification status of reports
    3. Confidence Level (20%): Average confidence score
    4. Geographic Impact (15%): Affected radius
    5. Ground Truth (15%): Official data confirmation
    
    Risk Levels:
    - LOW: 0-30
    - MODERATE: 31-60
    - HIGH: 61-85
    - CRITICAL: 86-100
    """
    
    def __init__(self):
        self.severity_weights = EVENT_SEVERITY_WEIGHTS
        logger.info("Weather Risk Detection Engine initialized")
    
    def assess_risk(self, event_data: Dict) -> RiskAssessment:
        """
        Assess risk level for a weather event.
        
        Args:
            event_data: Dictionary containing event cluster information
            
        Returns:
            RiskAssessment object with detailed risk analysis
        """
        event_id = event_data.get('event_id', 'unknown')
        event_type = event_data.get('event_type', 'unknown')
        
        logger.info(f"Assessing risk for event {event_id} ({event_type})")
        
        # Check for sufficient data
        if not self._has_sufficient_data(event_data):
            return self._create_insufficient_data_assessment(event_id, event_type)
        
        # Calculate individual risk factors
        factors = []
        
        # Factor 1: Event Severity (25%)
        severity_factor = self._assess_event_severity(event_type)
        factors.append(severity_factor)
        
        # Factor 2: Report Quality (25%)
        report_quality_factor = self._assess_report_quality(event_data)
        factors.append(report_quality_factor)
        
        # Factor 3: Confidence Level (20%)
        confidence_factor = self._assess_confidence_level(event_data)
        factors.append(confidence_factor)
        
        # Factor 4: Geographic Impact (15%)
        geographic_factor = self._assess_geographic_impact(event_data)
        factors.append(geographic_factor)
        
        # Factor 5: Ground Truth Verification (15%)
        ground_truth_factor = self._assess_ground_truth(event_data)
        factors.append(ground_truth_factor)
        
        # Calculate weighted risk score
        risk_score = self._calculate_risk_score(factors)
        risk_level = self._determine_risk_level(risk_score)
        
        # Generate explanation and recommendation
        explanation = self._generate_explanation(event_type, factors, risk_score, risk_level)
        recommended_action = self._generate_recommendation(risk_level, event_type)
        
        # Calculate overall confidence
        overall_confidence = event_data.get('avg_confidence_score', 0.5)
        
        # Convert factors to dict format
        factors_dict = [
            {
                'name': f.name,
                'value': f.value,
                'weight': f.weight,
                'description': f.description,
                'met': f.met
            }
            for f in factors
        ]
        
        assessment = RiskAssessment(
            event_id=event_id,
            event_type=event_type,
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            factors=factors_dict,
            explanation=explanation,
            recommended_action=recommended_action,
            confidence=round(overall_confidence, 4),
            assessed_at=datetime.utcnow(),
            insufficient_data=False
        )
        
        logger.info(f"Risk assessment complete: {risk_level} ({risk_score:.2f}/100)")
        
        return assessment
    
    def _has_sufficient_data(self, event_data: Dict) -> bool:
        """Check if event has sufficient data for risk assessment"""
        required_fields = ['event_id', 'event_type', 'report_count']
        return all(field in event_data for field in required_fields)
    
    def _create_insufficient_data_assessment(self, event_id: str, event_type: str) -> RiskAssessment:
        """Create assessment for insufficient data case"""
        return RiskAssessment(
            event_id=event_id,
            event_type=event_type,
            risk_score=0.0,
            risk_level='UNKNOWN',
            factors=[],
            explanation="Insufficient data available for risk assessment",
            recommended_action="Gather more information before taking action",
            confidence=0.0,
            assessed_at=datetime.utcnow(),
            insufficient_data=True
        )
    
    def _assess_event_severity(self, event_type: str) -> RiskFactor:
        """Assess inherent severity of event type"""
        severity = self.severity_weights.get(event_type.lower(), 0.5)
        
        return RiskFactor(
            name='Event Severity',
            value=severity,
            weight=0.25,
            description=f'{event_type.title()} events have {"high" if severity > 0.7 else "moderate" if severity > 0.5 else "low"} inherent severity',
            met=severity > 0.6
        )
    
    def _assess_report_quality(self, event_data: Dict) -> RiskFactor:
        """Assess quality based on number and verification of reports"""
        report_count = event_data.get('report_count', 0)
        verified_count = event_data.get('verification_summary', {}).get('verified', 0)
        disputed_count = event_data.get('verification_summary', {}).get('disputed', 0)
        fake_count = event_data.get('verification_summary', {}).get('fake', 0)
        
        # Calculate report concentration score (0.0 to 1.0)
        if report_count >= 20:
            concentration = 1.0
        elif report_count >= 10:
            concentration = 0.8
        elif report_count >= 5:
            concentration = 0.6
        elif report_count >= 3:
            concentration = 0.4
        else:
            concentration = 0.2
        
        # Calculate verification quality (0.0 to 1.0)
        if report_count > 0:
            verification_ratio = verified_count / report_count
            # Penalize for fakes and disputes
            penalty = (fake_count * 0.3 + disputed_count * 0.1) / report_count
            verification_quality = max(0.0, verification_ratio - penalty)
        else:
            verification_quality = 0.0
        
        # Combined score
        quality_score = (concentration * 0.5 + verification_quality * 0.5)
        
        description = f"{report_count} reports detected, {verified_count} verified"
        if fake_count > 0:
            description += f", {fake_count} flagged as fake"
        
        return RiskFactor(
            name='Report Quality',
            value=quality_score,
            weight=0.25,
            description=description,
            met=quality_score > 0.6
        )
    
    def _assess_confidence_level(self, event_data: Dict) -> RiskFactor:
        """Assess average confidence level"""
        avg_confidence = event_data.get('avg_confidence_score', 0.0)
        
        confidence_level = "high" if avg_confidence > 0.7 else "moderate" if avg_confidence > 0.5 else "low"
        
        return RiskFactor(
            name='Confidence Level',
            value=avg_confidence,
            weight=0.20,
            description=f"Average confidence score: {avg_confidence * 100:.1f}% ({confidence_level})",
            met=avg_confidence > 0.7
        )
    
    def _assess_geographic_impact(self, event_data: Dict) -> RiskFactor:
        """Assess geographic spread of event"""
        affected_radius_km = event_data.get('affected_radius_km', 0.0)
        
        # Normalize radius to 0.0-1.0 scale (larger = higher risk)
        if affected_radius_km >= 20:
            impact = 1.0
        elif affected_radius_km >= 10:
            impact = 0.8
        elif affected_radius_km >= 5:
            impact = 0.6
        elif affected_radius_km >= 1:
            impact = 0.4
        else:
            impact = 0.2
        
        impact_level = "large" if impact > 0.7 else "moderate" if impact > 0.4 else "small"
        
        return RiskFactor(
            name='Geographic Impact',
            value=impact,
            weight=0.15,
            description=f"Affected radius: {affected_radius_km:.1f} km ({impact_level} area)",
            met=impact > 0.6
        )
    
    def _assess_ground_truth(self, event_data: Dict) -> RiskFactor:
        """Assess ground truth verification from official sources"""
        # This would check if reports have ground truth verification signals
        # For now, we'll estimate based on verified reports
        verified_count = event_data.get('verification_summary', {}).get('verified', 0)
        report_count = event_data.get('report_count', 1)
        
        verification_ratio = verified_count / report_count if report_count > 0 else 0.0
        
        # Ground truth is strong if most reports are verified
        ground_truth_score = verification_ratio
        
        status = "confirmed" if ground_truth_score > 0.7 else "partial" if ground_truth_score > 0.4 else "unconfirmed"
        
        return RiskFactor(
            name='Ground Truth Verification',
            value=ground_truth_score,
            weight=0.15,
            description=f"Ground truth: {status} ({verified_count}/{report_count} verified)",
            met=ground_truth_score > 0.6
        )
    
    def _calculate_risk_score(self, factors: List[RiskFactor]) -> float:
        """Calculate weighted risk score (0-100)"""
        total_score = sum(factor.value * factor.weight for factor in factors)
        total_weight = sum(factor.weight for factor in factors)
        
        # Normalize to 0-100 scale
        risk_score = (total_score / total_weight) * 100 if total_weight > 0 else 0.0
        
        return risk_score
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level based on score"""
        if risk_score >= 86:
            return 'CRITICAL'
        elif risk_score >= 61:
            return 'HIGH'
        elif risk_score >= 31:
            return 'MODERATE'
        else:
            return 'LOW'
    
    def _generate_explanation(self, event_type: str, factors: List[RiskFactor],
                            risk_score: float, risk_level: str) -> str:
        """Generate human-readable explanation"""
        met_factors = [f for f in factors if f.met]
        
        explanation = f"{risk_level} RISK - {event_type.title()} Event\n\n"
        explanation += f"Risk Score: {risk_score:.1f}/100\n\n"
        
        if met_factors:
            explanation += "Key Risk Factors:\n"
            for factor in met_factors:
                explanation += f"✓ {factor.description}\n"
        else:
            explanation += "No significant risk factors identified.\n"
        
        return explanation.strip()
    
    def _generate_recommendation(self, risk_level: str, event_type: str) -> str:
        """Generate recommended action based on risk level"""
        recommendations = {
            'CRITICAL': f"IMMEDIATE ACTION REQUIRED: Deploy emergency response teams. "
                       f"Evacuate affected areas if necessary. "
                       f"Issue public warnings through all available channels.",
            
            'HIGH': f"Monitor the affected area closely and prepare emergency response resources. "
                   f"Alert local authorities and emergency services. "
                   f"Consider issuing public advisories.",
            
            'MODERATE': f"Continue monitoring the situation. "
                       f"Inform relevant local authorities. "
                       f"Prepare response plans if conditions worsen.",
            
            'LOW': f"Routine monitoring sufficient. "
                  f"No immediate action required at this time."
        }
        
        return recommendations.get(risk_level, "Assess situation and determine appropriate response.")


def get_risk_detection_engine() -> WeatherRiskDetectionEngine:
    """Get singleton instance of risk detection engine"""
    return WeatherRiskDetectionEngine()
