"""
Tests for text embedding deduplication (Signal 3).

Tests the text_dedup_check function and TextDeduplicator class.

Note: These tests use simplified models without PostGIS for SQLite compatibility.
"""

import pytest
import json
from datetime import datetime, timedelta
from sqlalchemy import select
from app.ml.deduplicator import (
    TextDeduplicator,
    TextDeduplicationResult,
    get_deduplicator,
    text_dedup_check
)


# Import deduplicator module for patching
from app.ml import deduplicator as deduplicator_module


# Use test models from conftest
from tests.conftest import (
    WeatherReportTest as WeatherReport,
    EventClusterTest as EventCluster,
    VerificationLogTest as VerificationLog
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def deduplicator():
    """Create a TextDeduplicator instance for testing."""
    return TextDeduplicator()


# ============================================================================
# Test: Embedding Computation
# ============================================================================

def test_compute_embedding_success(deduplicator):
    """Test that embedding computation works."""
    text = "Heavy rainfall reported in Mumbai causing flooding"
    embedding = deduplicator.compute_embedding(text)
    
    # Check embedding dimensions (all-MiniLM-L6-v2 produces 384-dim vectors)
    assert embedding.shape == (384,)
    
    # Check that embedding contains valid floats
    assert embedding.dtype.kind == 'f'  # float type


def test_compute_embedding_empty_text(deduplicator):
    """Test that empty text raises ValueError."""
    with pytest.raises(ValueError, match="Cannot compute embedding for empty text"):
        deduplicator.compute_embedding("")
    
    with pytest.raises(ValueError, match="Cannot compute embedding for empty text"):
        deduplicator.compute_embedding("   ")


def test_compute_embedding_whitespace_normalization(deduplicator):
    """Test that whitespace is normalized before embedding."""
    text1 = "Heavy   rainfall  in Mumbai"
    text2 = "Heavy rainfall in Mumbai"
    
    embedding1 = deduplicator.compute_embedding(text1)
    embedding2 = deduplicator.compute_embedding(text2)
    
    # Should be identical after normalization
    similarity = deduplicator.cosine_similarity(embedding1, embedding2)
    assert similarity > 0.99


# ============================================================================
# Test: Cosine Similarity
# ============================================================================

def test_cosine_similarity_identical_vectors(deduplicator):
    """Test cosine similarity with identical vectors."""
    text = "Heavy rainfall in Mumbai"
    embedding = deduplicator.compute_embedding(text)
    
    similarity = deduplicator.cosine_similarity(embedding, embedding)
    assert abs(similarity - 1.0) < 0.001  # Should be 1.0


def test_cosine_similarity_similar_texts(deduplicator):
    """Test cosine similarity with similar texts."""
    text1 = "Heavy rainfall in Mumbai causing severe flooding"
    text2 = "Intense rain in Mumbai leads to major floods"
    
    embedding1 = deduplicator.compute_embedding(text1)
    embedding2 = deduplicator.compute_embedding(text2)
    
    similarity = deduplicator.cosine_similarity(embedding1, embedding2)
    
    # Similar texts should have high similarity (> 0.7)
    assert similarity > 0.7


def test_cosine_similarity_different_texts(deduplicator):
    """Test cosine similarity with completely different texts."""
    text1 = "Heavy rainfall in Mumbai causing flooding"
    text2 = "Sunny weather in Delhi with clear skies"
    
    embedding1 = deduplicator.compute_embedding(text1)
    embedding2 = deduplicator.compute_embedding(text2)
    
    similarity = deduplicator.cosine_similarity(embedding1, embedding2)
    
    # Different texts should have lower similarity
    assert similarity < 0.6


# ============================================================================
# Test: Duplicate Detection Logic
# ============================================================================

@pytest.mark.asyncio
async def test_check_text_unique_no_existing_reports(db_session, deduplicator):
    """Test checking text when no similar reports exist."""
    # Create a report
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall in Mumbai causing flooding",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Check for duplicates
    result = await deduplicator.check_text(db_session, report.raw_text, report, merge_duplicates=False)
    
    assert result.is_duplicate is False
    assert result.confidence == 1.0
    assert result.cluster_id is None
    assert result.closest_match_id is None
    assert "No similar reports found" in result.reasoning


@pytest.mark.asyncio
async def test_check_text_exact_duplicate(db_session, deduplicator):
    """Test detecting exact duplicate text."""
    text = "Heavy rainfall in Mumbai causing severe flooding"
    
    # Create first report
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text=text,
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    # Create second report with same text
    report2 = WeatherReport(
        source_type="twitter",
        raw_text=text,
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check for duplicates
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=False)
    
    assert result.is_duplicate is True
    assert result.confidence == 0.0
    assert result.closest_match_similarity >= 0.98  # Should be very high
    assert "Duplicate detected" in result.reasoning


@pytest.mark.asyncio
async def test_check_text_similar_but_not_duplicate(db_session, deduplicator):
    """Test detecting similar but not duplicate text."""
    # Create first report
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall in Mumbai causing severe flooding on roads",
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=2)
    )
    db_session.add(report1)
    await db_session.commit()
    
    # Create second report with similar but different text
    report2 = WeatherReport(
        source_type="twitter",
        raw_text="Strong winds and thunderstorm in Mumbai affecting traffic",
        event_type="thunderstorm",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check for duplicates
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=False)
    
    # Should not be marked as duplicate (similarity likely 0.7-0.85)
    assert result.is_duplicate is False
    assert result.confidence > 0.0  # Some confidence penalty
    assert result.closest_match_similarity is not None


@pytest.mark.asyncio
async def test_check_text_near_duplicate_high_similarity(db_session, deduplicator):
    """Test detecting near-duplicate with similarity > 0.92."""
    # Create first report
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall in Mumbai causing severe flooding",
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    # Create second report with paraphrased text (same meaning)
    report2 = WeatherReport(
        source_type="twitter",
        raw_text="Intense rain in Mumbai leading to serious floods",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check for duplicates
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=False)
    
    # Similarity should be high (> 0.85)
    assert result.closest_match_similarity > 0.85


# ============================================================================
# Test: Clustering (Merging Duplicates)
# ============================================================================

@pytest.mark.asyncio
async def test_merge_into_cluster_creates_new_cluster(db_session, deduplicator):
    """Test that merge_into_cluster creates a new cluster."""
    # Create first report
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall in Mumbai",
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    await db_session.refresh(report1)
    
    # Create second report (duplicate)
    report2 = WeatherReport(
        source_type="twitter",
        raw_text="Heavy rainfall in Mumbai",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Merge into cluster
    cluster_id = await deduplicator.merge_into_cluster(db_session, report2, report1)
    await db_session.commit()
    
    # Verify cluster was created
    assert cluster_id is not None
    
    # Verify cluster exists in database
    query = select(EventCluster).where(EventCluster.id == cluster_id)
    result = await db_session.execute(query)
    cluster = result.scalar_one_or_none()
    
    assert cluster is not None
    assert cluster.event_type == "flooding"
    assert cluster.report_count == 2
    
    # Verify both reports are assigned to cluster
    await db_session.refresh(report1)
    await db_session.refresh(report2)
    assert str(report1.cluster_id) == cluster_id
    assert str(report2.cluster_id) == cluster_id


@pytest.mark.asyncio
async def test_merge_into_existing_cluster(db_session, deduplicator):
    """Test merging into an existing cluster."""
    # Create cluster
    cluster = EventCluster(
        event_type="flooding",
        canonical_text="Heavy rainfall in Mumbai",
        report_count=1,
        first_reported_at=datetime.utcnow() - timedelta(hours=2),
        last_reported_at=datetime.utcnow() - timedelta(hours=2)
    )
    db_session.add(cluster)
    await db_session.commit()
    await db_session.refresh(cluster)
    
    # Create first report assigned to cluster
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall in Mumbai",
        event_type="flooding",
        cluster_id=cluster.id,
        reported_at=datetime.utcnow() - timedelta(hours=2)
    )
    db_session.add(report1)
    await db_session.commit()
    
    # Create second report (duplicate)
    report2 = WeatherReport(
        source_type="twitter",
        raw_text="Heavy rainfall in Mumbai",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Merge into existing cluster
    cluster_id = await deduplicator.merge_into_cluster(db_session, report2, report1)
    await db_session.commit()
    
    # Verify it used the existing cluster
    assert cluster_id == str(cluster.id)
    
    # Verify cluster count was incremented
    await db_session.refresh(cluster)
    assert cluster.report_count == 2
    
    # Verify report2 is assigned to cluster
    await db_session.refresh(report2)
    assert report2.cluster_id == cluster.id


@pytest.mark.asyncio
async def test_check_text_with_clustering_enabled(db_session, deduplicator):
    """Test that check_text creates clusters when merge_duplicates=True."""
    text = "Heavy rainfall in Mumbai causing flooding"
    
    # Create first report
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text=text,
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    # Create second report with same text
    report2 = WeatherReport(
        source_type="twitter",
        raw_text=text,
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check with clustering enabled
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=True)
    await db_session.commit()
    
    assert result.is_duplicate is True
    assert result.cluster_id is not None
    assert "merged into cluster" in result.reasoning


# ============================================================================
# Test: Time and Region Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_get_recent_reports_filters_by_time(db_session, deduplicator):
    """Test that get_recent_reports only returns reports within 24 hours."""
    # Create old report (25 hours ago)
    old_report = WeatherReport(
        source_type="citizen_form",
        raw_text="Old report",
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=25)
    )
    db_session.add(old_report)
    
    # Create recent report (2 hours ago)
    recent_report = WeatherReport(
        source_type="twitter",
        raw_text="Recent report",
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=2)
    )
    db_session.add(recent_report)
    await db_session.commit()
    
    # Create current report
    current_report = WeatherReport(
        source_type="citizen_form",
        raw_text="Current report",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(current_report)
    await db_session.commit()
    await db_session.refresh(current_report)
    
    # Get recent reports
    reports = await deduplicator.get_recent_reports(db_session, current_report)
    
    # Should only include recent report, not old report
    assert len(reports) == 1
    assert reports[0].id == recent_report.id


@pytest.mark.asyncio
async def test_get_recent_reports_filters_by_event_type(db_session, deduplicator):
    """Test that get_recent_reports filters by event type."""
    # Create flooding report
    flood_report = WeatherReport(
        source_type="citizen_form",
        raw_text="Flooding in area",
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(flood_report)
    
    # Create thunderstorm report
    storm_report = WeatherReport(
        source_type="twitter",
        raw_text="Thunderstorm nearby",
        event_type="thunderstorm",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(storm_report)
    await db_session.commit()
    
    # Create current flooding report
    current_report = WeatherReport(
        source_type="citizen_form",
        raw_text="More flooding",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(current_report)
    await db_session.commit()
    await db_session.refresh(current_report)
    
    # Get recent reports
    reports = await deduplicator.get_recent_reports(db_session, current_report)
    
    # Should only include flooding report
    assert len(reports) == 1
    assert reports[0].event_type == "flooding"


# ============================================================================
# Test: Full Integration (text_dedup_check)
# ============================================================================

@pytest.mark.asyncio
async def test_text_dedup_check_unique_report(db_session):
    """Test text_dedup_check with a unique report."""
    # Patch the module to use test models
    orig_wr = deduplicator_module.WeatherReport
    orig_vl = deduplicator_module.VerificationLog
    
    try:
        deduplicator_module.WeatherReport = WeatherReport
        deduplicator_module.VerificationLog = VerificationLog
        
        # Create a report
        report = WeatherReport(
            source_type="citizen_form",
            raw_text="Heavy rainfall in Mumbai causing flooding",
            event_type="flooding",
            reported_at=datetime.utcnow()
        )
        db_session.add(report)
        await db_session.commit()
        await db_session.refresh(report)
        
        # Run text dedup check
        result = await deduplicator_module.text_dedup_check(str(report.id), db_session)
        
        assert result.is_duplicate is False
        assert result.confidence == 1.0
        
        # Verify verification log was created
        query = select(VerificationLog).where(
            VerificationLog.report_id == report.id,
            VerificationLog.verification_step == "text_dedup_check"
        )
        log_result = await db_session.execute(query)
        log = log_result.scalar_one_or_none()
        
        assert log is not None
        result_data = json.loads(log.result)
        assert result_data["is_duplicate"] is False
        
        # Verify signals were updated
        await db_session.refresh(report)
        assert report.signals is not None
        signals_data = json.loads(report.signals)
        assert "text_dedup_signal" in signals_data
        assert signals_data["text_dedup_signal"]["confidence"] == 1.0
        
    finally:
        deduplicator_module.WeatherReport = orig_wr
        deduplicator_module.VerificationLog = orig_vl


@pytest.mark.asyncio
async def test_text_dedup_check_duplicate_report(db_session):
    """Test text_dedup_check with a duplicate report."""
    text = "Heavy rainfall in Mumbai causing severe flooding"
    
    # Create first report
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text=text,
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    # Create second report with same text
    report2 = WeatherReport(
        source_type="twitter",
        raw_text=text,
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Run text dedup check
    result = await text_dedup_check(str(report2.id), db_session)
    
    assert result.is_duplicate is True
    assert result.confidence == 0.0
    assert result.cluster_id is not None
    
    # Verify both reports are in the same cluster
    await db_session.refresh(report1)
    await db_session.refresh(report2)
    assert report1.cluster_id is not None
    assert report1.cluster_id == report2.cluster_id


@pytest.mark.asyncio
async def test_text_dedup_check_report_not_found(db_session):
    """Test text_dedup_check with non-existent report."""
    result = await text_dedup_check("00000000-0000-0000-0000-000000000000", db_session)
    
    assert result.is_duplicate is False
    assert result.confidence == 0.0
    assert "not found" in result.reasoning


@pytest.mark.asyncio
async def test_text_dedup_check_empty_text(db_session):
    """Test text_dedup_check with report that has no text."""
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="",
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    result = await text_dedup_check(str(report.id), db_session)
    
    assert result.is_duplicate is False
    assert result.confidence == 0.5
    assert "No text content" in result.reasoning


# ============================================================================
# Test: Result Serialization
# ============================================================================

def test_result_to_dict():
    """Test TextDeduplicationResult.to_dict()."""
    result = TextDeduplicationResult(
        is_duplicate=True,
        confidence=0.0,
        cluster_id="test-cluster-123",
        closest_match_id="test-report-456",
        closest_match_similarity=0.95,
        similar_report_count=3,
        reasoning="Duplicate detected"
    )
    
    result_dict = result.to_dict()
    
    assert result_dict["is_duplicate"] is True
    assert result_dict["confidence"] == 0.0
    assert result_dict["cluster_id"] == "test-cluster-123"
    assert result_dict["closest_match_id"] == "test-report-456"
    assert result_dict["closest_match_similarity"] == 0.95
    assert result_dict["similar_report_count"] == 3
    assert result_dict["reasoning"] == "Duplicate detected"


# ============================================================================
# Test: Global Deduplicator Instance
# ============================================================================

def test_get_deduplicator_singleton():
    """Test that get_deduplicator returns the same instance."""
    dedup1 = get_deduplicator()
    dedup2 = get_deduplicator()
    
    assert dedup1 is dedup2  # Should be the same object


# ============================================================================
# Test: Confidence Scoring
# ============================================================================

@pytest.mark.asyncio
async def test_confidence_score_duplicate(db_session, deduplicator):
    """Test confidence score for duplicate (similarity >= 0.92)."""
    text1 = "Heavy rainfall in Mumbai causing severe flooding"
    text2 = "Heavy rainfall in Mumbai causing severe flooding"
    
    # Create reports
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text=text1,
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    report2 = WeatherReport(
        source_type="twitter",
        raw_text=text2,
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=False)
    
    # Duplicate should have 0.0 confidence
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_confidence_score_similar(db_session, deduplicator):
    """Test confidence score for similar but not duplicate (0.85 < similarity < 0.92)."""
    # These texts are similar but not exact duplicates
    text1 = "Heavy rainfall in Mumbai causing severe flooding on roads and streets"
    text2 = "Intense rain in Mumbai city leading to major floods in multiple areas"
    
    # Create reports
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text=text1,
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    report2 = WeatherReport(
        source_type="twitter",
        raw_text=text2,
        event_type="flooding",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=False)
    
    # Similar should have reduced confidence (between 0.0 and 1.0)
    assert 0.0 < result.confidence < 1.0


@pytest.mark.asyncio
async def test_confidence_score_unique(db_session, deduplicator):
    """Test confidence score for unique text (similarity < 0.85)."""
    text1 = "Heavy rainfall in Mumbai causing flooding"
    text2 = "Sunny weather in Delhi with clear blue skies"
    
    # Create reports
    report1 = WeatherReport(
        source_type="citizen_form",
        raw_text=text1,
        event_type="flooding",
        reported_at=datetime.utcnow() - timedelta(hours=1)
    )
    db_session.add(report1)
    await db_session.commit()
    
    report2 = WeatherReport(
        source_type="twitter",
        raw_text=text2,
        event_type="heatwave",
        reported_at=datetime.utcnow()
    )
    db_session.add(report2)
    await db_session.commit()
    await db_session.refresh(report2)
    
    # Check
    result = await deduplicator.check_text(db_session, report2.raw_text, report2, merge_duplicates=False)
    
    # Unique should have full confidence
    assert result.confidence == 1.0
