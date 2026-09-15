"""
Confidence Score Calculation (Signal Aggregation)

Combines the three verification signals into a final confidence score:
- Signal 1: Ground-truth verification (weight: 0.5)
- Signal 2: Image pHash deduplication (weight: 0.3)
- Signal 3: Text embedding deduplication (weight: 0.2)

Formula: confidence = 0.5*S1 + 0.3*S2 + 0.2*S3

Thresholds:
- confidence > 0.7 → verified
- 0.4 <= confidence <= 0.7 → disputed
- confidence < 0.4 → fake
"""

import logging
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import models - these will be patched in tests
from app.models.weather_report import WeatherReport, VerificationLog

logger = logging.getLogger(__name__)


# Weights for each signal
WEIGHT_GROUND_TRUTH = 0.5
WEIGHT_IMAGE_HASH = 0.3
WEIGHT_TEXT_DEDUP = 0.2

# Verification status thresholds
THRESHOLD_VERIFIED = 0.7
THRESHOLD_DISPUTED = 0.4


@dataclass
class ConfidenceResult:
    """Result of confidence score calculation."""
    
    confidence: float
    verification_status: str
    signal_confidences: Dict[str, Optional[float]]
    weights_used: Dict[str, float]
    reasoning: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "confidence": self.confidence,
            "verification_status": self.verification_status,
            "signal_confidences": self.signal_confidences,
            "weights_used": self.weights_used,
            "reasoning": self.reasoning
        }


def determine_verification_status(confidence: float) -> str:
    """
    Determine verification status based on confidence score.
    
    Args:
        confidence: Confidence score (0.0-1.0)
        
    Returns:
        Verification status: 'verified', 'disputed', or 'fake'
    """
    if confidence > THRESHOLD_VERIFIED:
        return "verified"
    elif confidence >= THRESHOLD_DISPUTED:
        return "disputed"
    else:
        return "fake"


async def get_signal_confidence(
    db: AsyncSession,
    report_id: str,
    verification_step: str
) -> Optional[float]:
    """
    Get confidence score from a specific verification signal.
    
    Args:
        db: Database session
        report_id: Report UUID (as string)
        verification_step: Name of the verification step
        
    Returns:
        Confidence score or None if not found
    """
    # Cast report_id to string for SQLite compatibility  
    query = select(VerificationLog).where(
        VerificationLog.report_id == report_id,
        VerificationLog.verification_step == verification_step
    ).order_by(VerificationLog.executed_at.desc())
    
    result = await db.execute(query)
    log = result.scalars().first()  # Get the first (most recent) log
    
    if not log:
        return None
    
    try:
        # Parse result JSON
        if isinstance(log.result, str):
            result_data = json.loads(log.result)
        else:
            result_data = log.result
        
        # Extract confidence
        return result_data.get("confidence")
    except (json.JSONDecodeError, AttributeError, KeyError) as e:
        logger.warning(f"Failed to parse confidence from {verification_step}: {e}")
        return None


async def compute_confidence_score(
    report_id: str,
    db: AsyncSession
) -> ConfidenceResult:
    """
    Compute final confidence score by aggregating all verification signals.
    
    This is the main entry point for Phase 3.6 - it:
    1. Fetches all three signal results from verification_logs
    2. Computes weighted average
    3. Handles missing signals by renormalizing weights
    4. Determines verification status
    5. Updates the report in DB
    
    Args:
        report_id: UUID of the report to score
        db: Database session
        
    Returns:
        ConfidenceResult with final confidence and status
    """
    logger.info(f"Computing confidence score for report {report_id}")
    
    try:
        # Get the report
        query = select(WeatherReport).where(WeatherReport.id == report_id)
        result = await db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            logger.error(f"Report {report_id} not found")
            return ConfidenceResult(
                confidence=0.0,
                verification_status="fake",
                signal_confidences={},
                weights_used={},
                reasoning=f"Report {report_id} not found"
            )
        
        # Fetch each signal's confidence
        ground_truth_conf = await get_signal_confidence(db, report_id, "ground_truth_check")
        image_hash_conf = await get_signal_confidence(db, report_id, "image_hash_check")
        text_dedup_conf = await get_signal_confidence(db, report_id, "text_dedup_check")
        
        logger.info(f"Signal confidences - GT: {ground_truth_conf}, Image: {image_hash_conf}, Text: {text_dedup_conf}")
        
        # Build signal confidence dict
        signal_confidences = {
            "ground_truth": ground_truth_conf,
            "image_hash": image_hash_conf,
            "text_dedup": text_dedup_conf
        }
        
        # Handle missing signals by renormalizing weights
        weights = {
            "ground_truth": WEIGHT_GROUND_TRUTH,
            "image_hash": WEIGHT_IMAGE_HASH,
            "text_dedup": WEIGHT_TEXT_DEDUP
        }
        
        # Calculate total weight of available signals
        available_weight = 0.0
        weighted_sum = 0.0
        missing_signals = []
        
        if ground_truth_conf is not None:
            weighted_sum += weights["ground_truth"] * ground_truth_conf
            available_weight += weights["ground_truth"]
        else:
            missing_signals.append("ground_truth")
        
        if image_hash_conf is not None:
            weighted_sum += weights["image_hash"] * image_hash_conf
            available_weight += weights["image_hash"]
        else:
            missing_signals.append("image_hash")
        
        if text_dedup_conf is not None:
            weighted_sum += weights["text_dedup"] * text_dedup_conf
            available_weight += weights["text_dedup"]
        else:
            missing_signals.append("text_dedup")
        
        # Compute final confidence
        if available_weight > 0:
            # Normalize by available weight
            confidence = weighted_sum / available_weight
        else:
            # No signals available
            logger.warning(f"No verification signals available for report {report_id}")
            confidence = 0.5  # Default to uncertain
        
        # Clamp to valid range
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine verification status
        verification_status = determine_verification_status(confidence)
        
        # Build reasoning
        if missing_signals:
            reasoning = f"Computed from {len(signal_confidences) - len(missing_signals)} signals (missing: {', '.join(missing_signals)})"
        else:
            reasoning = "Computed from all 3 verification signals"
        
        # Calculate actual weights used (normalized)
        weights_used = {}
        if available_weight > 0:
            for signal, weight in weights.items():
                if signal_confidences[signal] is not None:
                    weights_used[signal] = weight / available_weight
                else:
                    weights_used[signal] = 0.0
        
        # Create result
        result = ConfidenceResult(
            confidence=confidence,
            verification_status=verification_status,
            signal_confidences=signal_confidences,
            weights_used=weights_used,
            reasoning=reasoning
        )
        
        # Update the report
        report.confidence_score = confidence
        report.verification_status = verification_status
        
        # Update signals JSONB
        if report.signals is None:
            report.signals = {}
        
        # Handle both JSONB (Postgres) and Text (SQLite) column types
        if isinstance(report.signals, str):
            signals_dict = json.loads(report.signals) if report.signals else {}
        else:
            signals_dict = report.signals if isinstance(report.signals, dict) else {}
        
        signals_dict["confidence_calculation"] = result.to_dict()
        
        # Always store as JSON string for compatibility with both SQLite and Postgres
        report.signals = json.dumps(signals_dict)
        
        # Store verification log
        log_entry = VerificationLog(
            report_id=report.id,
            verification_step="confidence_calculation",
            result=json.dumps(result.to_dict())
        )
        db.add(log_entry)
        
        # Commit changes
        await db.commit()
        
        logger.info(f"Confidence score computed for report {report_id}: "
                   f"{confidence:.2f} ({verification_status})")
        
        return result
    
    except Exception as e:
        logger.error(f"Confidence score calculation failed for report {report_id}: {e}")
        await db.rollback()
        raise


async def recompute_confidence_with_override(
    report_id: str,
    db: AsyncSession,
    admin_override_confidence: float
) -> ConfidenceResult:
    """
    Recompute confidence score with admin override.
    
    When an admin manually overrides the confidence, this function
    recalculates by giving the admin override a high weight.
    
    Args:
        report_id: UUID of the report
        db: Database session
        admin_override_confidence: Admin's confidence assessment (0.0-1.0)
        
    Returns:
        Updated ConfidenceResult
    """
    logger.info(f"Recomputing confidence with admin override for report {report_id}")
    
    # Get original confidence result
    original_result = await compute_confidence_score(report_id, db)
    
    # Blend admin override with original: 70% admin, 30% signals
    blended_confidence = 0.7 * admin_override_confidence + 0.3 * original_result.confidence
    blended_confidence = max(0.0, min(1.0, blended_confidence))
    
    verification_status = determine_verification_status(blended_confidence)
    
    # Update the report
    query = select(WeatherReport).where(WeatherReport.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    
    if report:
        report.confidence_score = blended_confidence
        report.verification_status = verification_status
        await db.commit()
    
    logger.info(f"Updated confidence with admin override: {blended_confidence:.2f}")
    
    return ConfidenceResult(
        confidence=blended_confidence,
        verification_status=verification_status,
        signal_confidences=original_result.signal_confidences,
        weights_used={"admin_override": 0.7, "signals": 0.3},
        reasoning=f"Blended with admin override (70% admin, 30% signals)"
    )
