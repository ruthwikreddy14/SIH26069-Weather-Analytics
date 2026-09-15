"""
Phase 3.8: Pipeline Integration

Integrates all verification signals into a single end-to-end verification workflow:
1. Ground-truth weather verification (Phase 3.2)
2. Image pHash deduplication (Phase 3.3)
3. Text embedding deduplication (Phase 3.4)
4. GPS spoofing detection (Phase 3.7)
5. Confidence score calculation (Phase 3.6)

This module provides the main verify_report() function that orchestrates
all verification steps and handles failures gracefully.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.weather_report import WeatherReport, VerificationLog
from app.ml.verifier import ground_truth_check
from app.ml.image_hash import image_hash_check
from app.ml.deduplicator import text_dedup_check
from app.ml.location_verifier import verify_location
from app.ml.confidence import compute_confidence_score

logger = logging.getLogger(__name__)


class PipelineResult:
    """Result of the complete verification pipeline."""
    
    def __init__(
        self,
        report_id: str,
        success: bool,
        confidence_score: float,
        verification_status: str,
        signals: Dict[str, Any],
        errors: Dict[str, str]
    ):
        self.report_id = report_id
        self.success = success
        self.confidence_score = confidence_score
        self.verification_status = verification_status
        self.signals = signals
        self.errors = errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "success": self.success,
            "confidence_score": self.confidence_score,
            "verification_status": self.verification_status,
            "signals": self.signals,
            "errors": self.errors
        }


async def verify_report(
    report_id: str,
    db: AsyncSession
) -> PipelineResult:
    """
    Execute the complete end-to-end verification pipeline.
    
    This is the main entry point for Phase 3.8 that integrates all verification
    components developed in Phases 3.2, 3.3, 3.4, 3.6, and 3.7.
    
    The pipeline executes in this order:
    1. Ground-truth weather verification (weight: 0.5)
    2. Image pHash deduplication (weight: 0.3, if image present)
    3. Text embedding deduplication (weight: 0.2)
    4. GPS spoofing detection
    5. Final confidence score calculation
    
    Each signal runs independently. If one signal fails, the pipeline continues
    with the remaining signals. The confidence score is computed using only
    the available signals with renormalized weights.
    
    Args:
        report_id: UUID of the weather report to verify
        db: Database session
        
    Returns:
        PipelineResult containing:
        - success: True if pipeline completed (even with some signal failures)
        - confidence_score: Final weighted confidence (0.0-1.0)
        - verification_status: "verified", "disputed", or "fake"
        - signals: Dict of individual signal results
        - errors: Dict of any errors encountered per signal
    """
    logger.info(f"Starting verification pipeline for report {report_id}")
    
    signals = {}
    errors = {}
    
    # Check if report exists
    try:
        query = select(WeatherReport).where(WeatherReport.id == report_id)
        result = await db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            logger.error(f"Report {report_id} not found")
            return PipelineResult(
                report_id=report_id,
                success=False,
                confidence_score=0.0,
                verification_status="unverified",
                signals={},
                errors={"pipeline": "Report not found"}
            )
    except Exception as e:
        logger.error(f"Error fetching report {report_id}: {str(e)}")
        return PipelineResult(
            report_id=report_id,
            success=False,
            confidence_score=0.0,
            verification_status="unverified",
            signals={},
            errors={"pipeline": f"Database error: {str(e)}"}
        )
    
    # Signal 1: Ground-truth weather verification (Phase 3.2)
    logger.info(f"[Pipeline] Step 1/5: Ground-truth verification for {report_id}")
    try:
        ground_truth_result = await ground_truth_check(report_id, db)
        signals["ground_truth"] = ground_truth_result.to_dict()
        
        if ground_truth_result.error:
            errors["ground_truth"] = ground_truth_result.error
            logger.warning(f"Ground-truth check failed: {ground_truth_result.error}")
        else:
            logger.info(f"Ground-truth check completed: confidence={ground_truth_result.confidence}")
    
    except Exception as e:
        error_msg = f"Ground-truth verification failed: {str(e)}"
        logger.error(error_msg)
        errors["ground_truth"] = error_msg
        signals["ground_truth"] = {"confidence": 0.5, "error": error_msg}
    
    # Signal 2: Image pHash deduplication (Phase 3.3)
    # Only run if report has images
    logger.info(f"[Pipeline] Step 2/5: Image hash check for {report_id}")
    try:
        # Check if report has images
        has_images = report.images is not None and len(report.images) > 0
        
        if has_images:
            image_hash_result = await image_hash_check(report_id, db)
            signals["image_hash"] = image_hash_result.to_dict()
            
            if image_hash_result.error:
                errors["image_hash"] = image_hash_result.error
                logger.warning(f"Image hash check failed: {image_hash_result.error}")
            else:
                logger.info(f"Image hash check completed: confidence={image_hash_result.confidence}")
        else:
            logger.info(f"No images found for report {report_id}, skipping image hash check")
            signals["image_hash"] = {"confidence": 0.5, "skipped": True, "reason": "No images present"}
    
    except Exception as e:
        error_msg = f"Image hash verification failed: {str(e)}"
        logger.error(error_msg)
        errors["image_hash"] = error_msg
        signals["image_hash"] = {"confidence": 0.5, "error": error_msg}
    
    # Signal 3: Text embedding deduplication (Phase 3.4)
    logger.info(f"[Pipeline] Step 3/5: Text deduplication check for {report_id}")
    try:
        text_dedup_result = await text_dedup_check(report_id, db)
        signals["text_dedup"] = text_dedup_result.to_dict()
        
        # Check if it's an error scenario based on confidence
        if text_dedup_result.confidence == 0.0 and text_dedup_result.reasoning:
            errors["text_dedup"] = text_dedup_result.reasoning
            logger.warning(f"Text dedup check failed: {text_dedup_result.reasoning}")
        else:
            logger.info(f"Text dedup check completed: confidence={text_dedup_result.confidence}")
    
    except Exception as e:
        error_msg = f"Text deduplication failed: {str(e)}"
        logger.error(error_msg)
        errors["text_dedup"] = error_msg
        signals["text_dedup"] = {"confidence": 0.5, "error": error_msg}
    
    # Step 4: GPS spoofing detection (Phase 3.7)
    logger.info(f"[Pipeline] Step 4/5: Location verification for {report_id}")
    try:
        location_result = await verify_location(report_id, db)
        signals["location"] = location_result.to_dict()
        
        if location_result.reasoning and "not found" in location_result.reasoning.lower():
            errors["location"] = location_result.reasoning
            logger.warning(f"Location verification failed: {location_result.reasoning}")
        else:
            logger.info(f"Location verification completed: source={location_result.location_source}, confidence={location_result.location_confidence}")
    
    except Exception as e:
        error_msg = f"Location verification failed: {str(e)}"
        logger.error(error_msg)
        errors["location"] = error_msg
        signals["location"] = {
            "location_source": "unknown",
            "location_confidence": "low",
            "error": error_msg
        }
    
    # Step 5: Compute final confidence score (Phase 3.6)
    logger.info(f"[Pipeline] Step 5/5: Computing confidence score for {report_id}")
    try:
        confidence_result = await compute_confidence_score(report_id, db)
        
        final_confidence = confidence_result.confidence
        final_status = confidence_result.verification_status
        
        logger.info(f"Confidence score computed: {final_confidence:.3f}, status={final_status}")
        
        # Add confidence breakdown to signals
        signals["confidence"] = confidence_result.to_dict()
    
    except Exception as e:
        error_msg = f"Confidence calculation failed: {str(e)}"
        logger.error(error_msg)
        errors["confidence"] = error_msg
        
        # Fallback: default to 0.5 confidence
        final_confidence = 0.5
        final_status = "disputed"
        signals["confidence"] = {
            "confidence": final_confidence,
            "verification_status": final_status,
            "error": error_msg
        }
    
    # Determine overall pipeline success
    # Pipeline succeeds if at least the confidence calculation completed
    pipeline_success = "confidence" not in errors
    
    logger.info(
        f"Pipeline completed for {report_id}: "
        f"success={pipeline_success}, confidence={final_confidence:.3f}, "
        f"status={final_status}, errors={len(errors)}"
    )
    
    return PipelineResult(
        report_id=report_id,
        success=pipeline_success,
        confidence_score=final_confidence,
        verification_status=final_status,
        signals=signals,
        errors=errors
    )


async def verify_report_batch(
    report_ids: list[str],
    db: AsyncSession
) -> list[PipelineResult]:
    """
    Verify multiple reports in batch.
    
    Useful for bulk verification or re-verification scenarios.
    Each report is verified independently - failures don't affect other reports.
    
    Args:
        report_ids: List of report UUIDs to verify
        db: Database session
        
    Returns:
        List of PipelineResult objects, one per report
    """
    logger.info(f"Starting batch verification for {len(report_ids)} reports")
    
    results = []
    for report_id in report_ids:
        try:
            result = await verify_report(report_id, db)
            results.append(result)
        except Exception as e:
            logger.error(f"Batch verification failed for {report_id}: {str(e)}")
            results.append(PipelineResult(
                report_id=report_id,
                success=False,
                confidence_score=0.0,
                verification_status="unverified",
                signals={},
                errors={"pipeline": f"Batch processing error: {str(e)}"}
            ))
    
    success_count = sum(1 for r in results if r.success)
    logger.info(f"Batch verification completed: {success_count}/{len(report_ids)} successful")
    
    return results
