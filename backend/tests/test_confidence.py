"""
Tests for confidence score calculation (Phase 3.6).

Tests the compute_confidence_score function and ConfidenceResult class.
"""

import pytest
import json
from datetime import datetime, timedelta
from sqlalchemy import select
from app.ml.confidence import (
    compute_confidence_score,
    determine_verification_status,
    get_signal_confidence,
    recompute_confidence_with_override,
    ConfidenceResult,
    WEIGHT_GROUND_TRUTH,
    WEIGHT_IMAGE_HASH,
    WEIGHT_TEXT_DEDUP,
    THRESHOLD_VERIFIED,
    THRESHOLD_DISPUTED
)

# Use test models from conftest
from tests.conftest import (
    WeatherReportTest as WeatherReport,
    VerificationLogTest as VerificationLog
)


# ============================================================================
# Test: Verification Status Determination
# ============================================================================

def test_determine_verification_status_verified():
    """Test status determination for verified reports."""
    assert determine_verification_status(0.85) == "verified"
    assert determine_verification_status(0.71) == "verified"
    assert determine_verification_status(1.0) == "verified"


def test_determine_verification_status_disputed():
    """Test status determination for disputed reports."""
    assert determine_verification_status(0.7) == "disputed"
    assert determine_verification_status(0.55) == "disputed"
    assert determine_verification_status(0.4) == "disputed"


def test_determine_verification_status_fake():
    """Test status determination for fake reports."""
    assert determine_verification_status(0.39) == "fake"
    assert determine_verification_status(0.2) == "fake"
    assert determine_verification_status(0.0) == "fake"


def test_determine_verification_status_boundaries():
    """Test exact threshold boundaries."""
    # > 0.7 is verified
    assert determine_verification_status(0.7001) == "verified"
    # <= 0.7 and >= 0.4 is disputed
    assert determine_verification_status(0.7000) == "disputed"
    assert determine_verification_status(0.4000) == "disputed"
    # < 0.4 is fake
    assert determine_verification_status(0.3999) == "fake"


# ============================================================================
# Test: Signal Confidence Extraction
# ============================================================================

@pytest.mark.asyncio
async def test_get_signal_confidence_exists(db_session):
    """Test getting signal confidence when log exists."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create verification log
    log = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps({"confidence": 0.8, "is_plausible": True})
    )
    db_session.add(log)
    await db_session.commit()
    
    # Get confidence
    confidence = await get_signal_confidence(db_session, str(report.id), "ground_truth_check")
    
    assert confidence == 0.8


@pytest.mark.asyncio
async def test_get_signal_confidence_not_found(db_session):
    """Test getting signal confidence when no log exists."""
    # Create report without logs
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Get confidence (should be None)
    confidence = await get_signal_confidence(db_session, str(report.id), "ground_truth_check")
    
    assert confidence is None


@pytest.mark.asyncio
async def test_get_signal_confidence_latest_log(db_session):
    """Test that latest log is used when multiple exist."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create old log
    log1 = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps({"confidence": 0.5})
    )
    db_session.add(log1)
    await db_session.commit()
    
    # Create newer log
    log2 = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps({"confidence": 0.9})
    )
    db_session.add(log2)
    await db_session.commit()
    
    # Should get latest confidence
    confidence = await get_signal_confidence(db_session, str(report.id), "ground_truth_check")
    
    assert confidence == 0.9


# ============================================================================
# Test: Full Confidence Calculation
# ============================================================================

@pytest.mark.asyncio
async def test_compute_confidence_all_signals(db_session):
    """Test confidence calculation with all three signals."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create all three signal logs
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 1.0, "is_plausible": True})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 1.0, "is_duplicate": False})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 1.0, "is_duplicate": False})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    # Compute confidence
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: 0.5*1.0 + 0.3*1.0 + 0.2*1.0 = 1.0
    assert result.confidence == 1.0
    assert result.verification_status == "verified"
    assert result.signal_confidences["ground_truth"] == 1.0
    assert result.signal_confidences["image_hash"] == 1.0
    assert result.signal_confidences["text_dedup"] == 1.0
    assert "all 3" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_compute_confidence_weighted_average(db_session):
    """Test weighted average calculation."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create signals with different confidences
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 0.8})  # weight 0.5
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 0.6})  # weight 0.3
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 1.0})  # weight 0.2
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    # Compute confidence
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: 0.5*0.8 + 0.3*0.6 + 0.2*1.0 = 0.4 + 0.18 + 0.2 = 0.78
    assert abs(result.confidence - 0.78) < 0.001
    assert result.verification_status == "verified"


@pytest.mark.asyncio
async def test_compute_confidence_missing_image(db_session):
    """Test confidence calculation when image signal is missing."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report without image",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create only ground_truth and text_dedup logs
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 0.8})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 1.0})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    # Compute confidence
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: (0.5*0.8 + 0.2*1.0) / (0.5 + 0.2) = (0.4 + 0.2) / 0.7 = 0.857...
    expected = (WEIGHT_GROUND_TRUTH * 0.8 + WEIGHT_TEXT_DEDUP * 1.0) / (WEIGHT_GROUND_TRUTH + WEIGHT_TEXT_DEDUP)
    assert abs(result.confidence - expected) < 0.001
    assert result.verification_status == "verified"
    assert result.signal_confidences["image_hash"] is None
    assert "missing" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_compute_confidence_only_ground_truth(db_session):
    """Test confidence calculation with only ground truth signal."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create only ground_truth log
    log = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps({"confidence": 0.6})
    )
    db_session.add(log)
    await db_session.commit()
    
    # Compute confidence
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: use ground_truth confidence directly (0.6)
    assert result.confidence == 0.6
    assert result.verification_status == "disputed"
    assert result.signal_confidences["ground_truth"] == 0.6
    assert result.signal_confidences["image_hash"] is None
    assert result.signal_confidences["text_dedup"] is None


@pytest.mark.asyncio
async def test_compute_confidence_no_signals(db_session):
    """Test confidence calculation when no signals are available."""
    # Create report without any logs
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Compute confidence
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: default to 0.5 (uncertain)
    assert result.confidence == 0.5
    assert result.verification_status == "disputed"


@pytest.mark.asyncio
async def test_compute_confidence_report_not_found(db_session):
    """Test confidence calculation for non-existent report."""
    # Try to compute confidence for non-existent report
    result = await compute_confidence_score("00000000-0000-0000-0000-000000000000", db_session)
    
    assert result.confidence == 0.0
    assert result.verification_status == "fake"
    assert "not found" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_compute_confidence_updates_report(db_session):
    """Test that compute_confidence updates the report fields."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create signals
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 0.9})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 0.8})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 0.7})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    # Compute confidence
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Refresh report and check updates
    await db_session.refresh(report)
    
    assert report.confidence_score is not None
    assert report.confidence_score == result.confidence
    assert report.verification_status == result.verification_status
    
    # Check signals were updated
    signals_data = json.loads(report.signals)
    assert "confidence_calculation" in signals_data
    assert signals_data["confidence_calculation"]["confidence"] == result.confidence


# ============================================================================
# Test: Verification Status Thresholds
# ============================================================================

@pytest.mark.asyncio
async def test_confidence_verified_threshold(db_session):
    """Test verified status (confidence > 0.7)."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create logs that result in confidence > 0.7
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 1.0})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 0.5})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 0.5})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: 0.5*1.0 + 0.3*0.5 + 0.2*0.5 = 0.5 + 0.15 + 0.1 = 0.75
    assert result.confidence == 0.75
    assert result.verification_status == "verified"


@pytest.mark.asyncio
async def test_confidence_disputed_threshold(db_session):
    """Test disputed status (0.4 <= confidence <= 0.7)."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create logs that result in confidence between 0.4 and 0.7
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 0.6})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 0.5})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 0.5})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: 0.5*0.6 + 0.3*0.5 + 0.2*0.5 = 0.3 + 0.15 + 0.1 = 0.55
    assert abs(result.confidence - 0.55) < 0.001
    assert result.verification_status == "disputed"


@pytest.mark.asyncio
async def test_confidence_fake_threshold(db_session):
    """Test fake status (confidence < 0.4)."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create logs that result in confidence < 0.4
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 0.2})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 0.3})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 0.4})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    result = await compute_confidence_score(str(report.id), db_session)
    
    # Expected: 0.5*0.2 + 0.3*0.3 + 0.2*0.4 = 0.1 + 0.09 + 0.08 = 0.27
    assert result.confidence == 0.27
    assert result.verification_status == "fake"


# ============================================================================
# Test: Edge Cases and Boundary Conditions
# ============================================================================

@pytest.mark.asyncio
async def test_confidence_clamped_to_range(db_session):
    """Test that confidence is clamped to [0.0, 1.0]."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create logs with maximum confidence
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 1.0})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 1.0})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 1.0})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    result = await compute_confidence_score(str(report.id), db_session)
    
    assert result.confidence == 1.0
    assert result.confidence <= 1.0
    assert result.confidence >= 0.0


@pytest.mark.asyncio
async def test_confidence_result_serialization(db_session):
    """Test ConfidenceResult to_dict serialization."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    log = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps({"confidence": 0.8})
    )
    db_session.add(log)
    await db_session.commit()
    
    result = await compute_confidence_score(str(report.id), db_session)
    result_dict = result.to_dict()
    
    assert "confidence" in result_dict
    assert "verification_status" in result_dict
    assert "signal_confidences" in result_dict
    assert "weights_used" in result_dict
    assert "reasoning" in result_dict
    
    # Should be JSON serializable
    json_str = json.dumps(result_dict)
    assert json_str is not None


@pytest.mark.asyncio
async def test_confidence_verification_log_created(db_session):
    """Test that a verification log is created for confidence calculation."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    log = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=json.dumps({"confidence": 0.8})
    )
    db_session.add(log)
    await db_session.commit()
    
    # Compute confidence
    await compute_confidence_score(str(report.id), db_session)
    
    # Check that confidence_calculation log was created
    query = select(VerificationLog).where(
        VerificationLog.report_id == report.id,
        VerificationLog.verification_step == "confidence_calculation"
    )
    result = await db_session.execute(query)
    log = result.scalar_one_or_none()
    
    assert log is not None
    log_data = json.loads(log.result)
    assert "confidence" in log_data
    assert "verification_status" in log_data


# ============================================================================
# Test: Admin Override
# ============================================================================

@pytest.mark.asyncio
async def test_recompute_with_admin_override(db_session):
    """Test confidence recomputation with admin override."""
    # Create report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        reported_at=datetime.utcnow(),
        admin_override=True
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Create signal logs
    logs = [
        VerificationLog(
            report_id=report.id,
            verification_step="ground_truth_check",
            result=json.dumps({"confidence": 0.5})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="image_hash_check",
            result=json.dumps({"confidence": 0.5})
        ),
        VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps({"confidence": 0.5})
        )
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    
    # Recompute with admin override
    result = await recompute_confidence_with_override(str(report.id), db_session, 0.9)
    
    # Expected: 0.7 * 0.9 + 0.3 * 0.5 = 0.63 + 0.15 = 0.78
    expected = 0.7 * 0.9 + 0.3 * 0.5
    assert abs(result.confidence - expected) < 0.001
    assert "admin override" in result.reasoning.lower()
