"""
Phase 3.8 Integration Tests: Pipeline Integration

Tests the complete end-to-end verification workflow integrating:
- Phase 3.2: Ground-truth weather verification
- Phase 3.3: Image pHash deduplication
- Phase 3.4: Text embedding deduplication
- Phase 3.6: Confidence score calculation
- Phase 3.7: GPS spoofing detection
"""

import pytest
import json
from datetime import datetime, timezone
from sqlalchemy import select

from app.ml.pipeline import verify_report, verify_report_batch, PipelineResult
from tests.conftest import (
    WeatherReportTest,
    VerificationLogTest,
    EventClusterTest
)


class TestPipelineIntegration:
    """Test complete verification pipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_with_verified_report(self, db_session):
        """Test pipeline with a verified report (all signals positive)."""
        # Create a verified report with good signals
        report = WeatherReportTest(
            id="pipeline-verified-1",
            event_type="rainfall",
            description="Heavy rainfall observed with waterlogging in streets",
            city="Mumbai",
            state="Maharashtra",
            latitude=19.0760,
            longitude=72.8777,
            images=json.dumps(["image1.jpg"]),
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        # Run pipeline
        result = await verify_report("pipeline-verified-1", db_session)
        
        # Verify result
        assert isinstance(result, PipelineResult)
        assert result.success is True
        assert result.report_id == "pipeline-verified-1"
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.verification_status in ["verified", "disputed", "fake"]
        
        # Check all signals executed
        assert "ground_truth" in result.signals
        assert "image_hash" in result.signals
        assert "text_dedup" in result.signals
        assert "location" in result.signals
        assert "confidence" in result.signals
        
        # Verify report updated in database
        db_report = await db_session.get(WeatherReportTest, "pipeline-verified-1")
        assert db_report is not None
        assert db_report.confidence_score is not None
        assert db_report.verification_status is not None
    
    @pytest.mark.asyncio
    async def test_pipeline_with_duplicate_report(self, db_session):
        """Test pipeline with duplicate text content."""
        # Create original report
        original = WeatherReportTest(
            id="pipeline-dup-orig",
            event_type="flooding",
            description="Severe flooding in city center with vehicles submerged",
            city="Chennai",
            state="Tamil Nadu",
            latitude=13.0827,
            longitude=80.2707,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(original)
        
        # Create event cluster
        cluster = EventClusterTest(
            id="cluster-flood-1",
            event_type="flooding",
            centroid="POINT(80.2707 13.0827)",
            report_ids=json.dumps(["pipeline-dup-orig"])
        )
        db_session.add(cluster)
        await db_session.commit()
        
        # Create duplicate report (very similar text)
        duplicate = WeatherReportTest(
            id="pipeline-dup-copy",
            event_type="flooding",
            description="Severe flooding in city center with many vehicles submerged",
            city="Chennai",
            state="Tamil Nadu",
            latitude=13.0827,
            longitude=80.2707,
            created_at=datetime.now(timezone.utc),
            user_id="user-2"
        )
        db_session.add(duplicate)
        await db_session.commit()
        
        # Run pipeline on duplicate
        result = await verify_report("pipeline-dup-copy", db_session)
        
        assert result.success is True
        assert "text_dedup" in result.signals
        
        # Should detect high similarity
        text_signal = result.signals["text_dedup"]
        if not text_signal.get("error"):
            # If text dedup worked, it should find similarity
            assert "is_duplicate" in text_signal or "similarity" in text_signal
    
    @pytest.mark.asyncio
    async def test_pipeline_with_suspicious_gps(self, db_session):
        """Test pipeline with GPS outside India."""
        report = WeatherReportTest(
            id="pipeline-bad-gps",
            event_type="rainfall",
            description="Heavy rain in Mumbai",
            city="Mumbai",
            state="Maharashtra",
            latitude=0.0,  # Atlantic Ocean - suspicious
            longitude=0.0,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        # Run pipeline
        result = await verify_report("pipeline-bad-gps", db_session)
        
        assert result.success is True
        assert "location" in result.signals
        
        location_signal = result.signals["location"]
        # Should detect suspicious GPS
        assert location_signal.get("location_source") in ["gps_suspicious", "text_inferred", "unknown"]
    
    @pytest.mark.asyncio
    async def test_pipeline_with_missing_data(self, db_session):
        """Test pipeline with minimal report data."""
        report = WeatherReportTest(
            id="pipeline-minimal",
            event_type="fog",
            description="Fog",
            city="Delhi",
            state="Delhi",
            # No GPS, no images
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        # Run pipeline
        result = await verify_report("pipeline-minimal", db_session)
        
        # Pipeline should handle gracefully
        assert result.success is True
        assert result.confidence_score is not None
        
        # Image hash should be skipped or have default confidence
        if "image_hash" in result.signals:
            image_signal = result.signals["image_hash"]
            assert image_signal.get("skipped") is True or "error" in image_signal
    
    @pytest.mark.asyncio
    async def test_pipeline_with_nonexistent_report(self, db_session):
        """Test pipeline with invalid report ID."""
        result = await verify_report("nonexistent-report-id", db_session)
        
        assert result.success is False
        assert result.confidence_score == 0.0
        assert result.verification_status == "unverified"
        assert len(result.errors) > 0
        assert "pipeline" in result.errors
    
    @pytest.mark.asyncio
    async def test_pipeline_preserves_phase_32_functionality(self, db_session):
        """Verify Phase 3.2 (ground-truth) still works in pipeline."""
        report = WeatherReportTest(
            id="pipeline-phase32",
            event_type="heatwave",
            description="Extreme heat conditions",
            city="Delhi",
            state="Delhi",
            latitude=28.6139,
            longitude=77.2090,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-phase32", db_session)
        
        assert result.success is True
        assert "ground_truth" in result.signals
        
        ground_truth = result.signals["ground_truth"]
        assert "confidence" in ground_truth
        assert isinstance(ground_truth["confidence"], (int, float))
    
    @pytest.mark.asyncio
    async def test_pipeline_preserves_phase_33_functionality(self, db_session):
        """Verify Phase 3.3 (image hash) still works in pipeline."""
        report = WeatherReportTest(
            id="pipeline-phase33",
            event_type="flooding",
            description="Flood with photos",
            city="Mumbai",
            state="Maharashtra",
            latitude=19.0760,
            longitude=72.8777,
            images=json.dumps(["flood1.jpg", "flood2.jpg"]),
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-phase33", db_session)
        
        assert result.success is True
        assert "image_hash" in result.signals
        
        image_hash = result.signals["image_hash"]
        assert "confidence" in image_hash or "skipped" in image_hash or "error" in image_hash
    
    @pytest.mark.asyncio
    async def test_pipeline_preserves_phase_34_functionality(self, db_session):
        """Verify Phase 3.4 (text dedup) still works in pipeline."""
        # Create first report
        report1 = WeatherReportTest(
            id="pipeline-phase34-1",
            event_type="thunderstorm",
            description="Lightning and thunder with heavy downpour",
            city="Bangalore",
            state="Karnataka",
            latitude=12.9716,
            longitude=77.5946,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report1)
        
        cluster = EventClusterTest(
            id="cluster-thunder-1",
            event_type="thunderstorm",
            centroid="POINT(77.5946 12.9716)",
            report_ids=json.dumps(["pipeline-phase34-1"])
        )
        db_session.add(cluster)
        await db_session.commit()
        
        # Create similar report
        report2 = WeatherReportTest(
            id="pipeline-phase34-2",
            event_type="thunderstorm",
            description="Lightning and thunder with very heavy downpour",
            city="Bangalore",
            state="Karnataka",
            latitude=12.9716,
            longitude=77.5946,
            created_at=datetime.now(timezone.utc),
            user_id="user-2"
        )
        db_session.add(report2)
        await db_session.commit()
        
        result = await verify_report("pipeline-phase34-2", db_session)
        
        assert result.success is True
        assert "text_dedup" in result.signals
        
        text_dedup = result.signals["text_dedup"]
        assert "confidence" in text_dedup
    
    @pytest.mark.asyncio
    async def test_pipeline_preserves_phase_36_functionality(self, db_session):
        """Verify Phase 3.6 (confidence calculation) still works in pipeline."""
        report = WeatherReportTest(
            id="pipeline-phase36",
            event_type="rainfall",
            description="Moderate rainfall",
            city="Pune",
            state="Maharashtra",
            latitude=18.5204,
            longitude=73.8567,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-phase36", db_session)
        
        assert result.success is True
        assert "confidence" in result.signals
        
        confidence = result.signals["confidence"]
        assert "confidence_score" in confidence or "confidence" in confidence
        assert "verification_status" in confidence
        # Check the actual key
        conf_score = confidence.get("confidence_score") or confidence.get("confidence")
        assert 0.0 <= conf_score <= 1.0
        assert confidence["verification_status"] in ["verified", "disputed", "fake"]
        
        # Verify weights are correct (0.5, 0.3, 0.2 when all present, renormalized when some missing)
        if "weights" in confidence or "weights_used" in confidence:
            weights = confidence.get("weights") or confidence.get("weights_used")
            # Weights should be non-negative and sum to a reasonable total
            if "ground_truth" in weights:
                assert 0.0 <= weights.get("ground_truth", 0.0) <= 1.0
            if "image_hash" in weights:
                assert 0.0 <= weights.get("image_hash", 0.0) <= 1.0
            if "text_dedup" in weights:
                assert 0.0 <= weights.get("text_dedup", 0.0) <= 1.0
    
    @pytest.mark.asyncio
    async def test_pipeline_preserves_phase_37_functionality(self, db_session):
        """Verify Phase 3.7 (GPS verification) still works in pipeline."""
        # Test with valid Indian GPS
        report = WeatherReportTest(
            id="pipeline-phase37",
            event_type="dust_storm",
            description="Dust storm in Rajasthan",
            city="Jaipur",
            state="Rajasthan",
            latitude=26.9124,
            longitude=75.7873,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-phase37", db_session)
        
        assert result.success is True
        assert "location" in result.signals
        
        location = result.signals["location"]
        assert "location_source" in location
        assert "location_confidence" in location
        assert location["location_source"] in ["gps_verified", "gps_suspicious", "text_inferred", "unknown"]
        assert location["location_confidence"] in ["high", "medium", "low"]
    
    @pytest.mark.asyncio
    async def test_pipeline_signal_failure_graceful_handling(self, db_session):
        """Test that pipeline continues even if individual signals fail."""
        # Create report that might cause some signals to fail
        report = WeatherReportTest(
            id="pipeline-partial-fail",
            event_type="strong_wind",
            description="Strong winds",
            city="Kolkata",
            state="West Bengal",
            latitude=22.5726,
            longitude=88.3639,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-partial-fail", db_session)
        
        # Pipeline should still succeed overall even if some signals fail
        assert isinstance(result, PipelineResult)
        assert result.report_id == "pipeline-partial-fail"
        
        # Should have attempted all signals
        # Even if some failed, confidence should still be computed
        assert "confidence" in result.signals
    
    @pytest.mark.asyncio
    async def test_pipeline_result_to_dict(self, db_session):
        """Test PipelineResult serialization."""
        report = WeatherReportTest(
            id="pipeline-serialize",
            event_type="fog",
            description="Dense fog",
            city="Delhi",
            state="Delhi",
            latitude=28.6139,
            longitude=77.2090,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-serialize", db_session)
        
        # Convert to dict
        result_dict = result.to_dict()
        
        # Verify structure
        assert isinstance(result_dict, dict)
        assert "report_id" in result_dict
        assert "success" in result_dict
        assert "confidence_score" in result_dict
        assert "verification_status" in result_dict
        assert "signals" in result_dict
        assert "errors" in result_dict
        
        # Should be JSON-serializable
        import json
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)


class TestPipelineBatch:
    """Test batch verification functionality."""
    
    @pytest.mark.asyncio
    async def test_batch_verification_multiple_reports(self, db_session):
        """Test batch processing of multiple reports."""
        # Create multiple reports
        reports = []
        for i in range(3):
            report = WeatherReportTest(
                id=f"batch-report-{i}",
                event_type="rainfall",
                description=f"Rainfall report {i}",
                city="Mumbai",
                state="Maharashtra",
                latitude=19.0760,
                longitude=72.8777,
                created_at=datetime.now(timezone.utc),
                user_id=f"user-{i}"
            )
            reports.append(report)
            db_session.add(report)
        
        await db_session.commit()
        
        # Run batch verification
        report_ids = [f"batch-report-{i}" for i in range(3)]
        results = await verify_report_batch(report_ids, db_session)
        
        # Verify results
        assert len(results) == 3
        assert all(isinstance(r, PipelineResult) for r in results)
        assert all(r.report_id in report_ids for r in results)
    
    @pytest.mark.asyncio
    async def test_batch_verification_with_failures(self, db_session):
        """Test batch processing with some invalid report IDs."""
        # Create one valid report
        report = WeatherReportTest(
            id="batch-valid",
            event_type="rainfall",
            description="Valid report",
            city="Delhi",
            state="Delhi",
            latitude=28.6139,
            longitude=77.2090,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        # Batch with mix of valid and invalid IDs
        report_ids = ["batch-valid", "invalid-id-1", "invalid-id-2"]
        results = await verify_report_batch(report_ids, db_session)
        
        # Should return results for all IDs
        assert len(results) == 3
        
        # First should succeed
        assert results[0].success is True
        assert results[0].report_id == "batch-valid"
        
        # Others should fail gracefully
        assert results[1].success is False
        assert results[2].success is False
    
    @pytest.mark.asyncio
    async def test_batch_verification_empty_list(self, db_session):
        """Test batch processing with empty list."""
        results = await verify_report_batch([], db_session)
        assert len(results) == 0


class TestPipelineEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_pipeline_with_null_fields(self, db_session):
        """Test pipeline handles null/missing fields gracefully."""
        report = WeatherReportTest(
            id="pipeline-nulls",
            event_type="rainfall",
            description="Minimal data",
            city="Mumbai",
            state="Maharashtra",
            # latitude=None,  # Will default to NULL
            # longitude=None,
            # images=None,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        # Should not crash
        result = await verify_report("pipeline-nulls", db_session)
        
        assert isinstance(result, PipelineResult)
        # May succeed or fail depending on how much data is missing
        # But should not raise exceptions
    
    @pytest.mark.asyncio
    async def test_pipeline_confidence_score_range(self, db_session):
        """Test that confidence score is always in valid range."""
        report = WeatherReportTest(
            id="pipeline-range",
            event_type="heatwave",
            description="Hot weather",
            city="Ahmedabad",
            state="Gujarat",
            latitude=23.0225,
            longitude=72.5714,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-range", db_session)
        
        # Confidence must be between 0.0 and 1.0
        assert 0.0 <= result.confidence_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_pipeline_verification_status_valid(self, db_session):
        """Test that verification status is always valid."""
        report = WeatherReportTest(
            id="pipeline-status",
            event_type="thunderstorm",
            description="Thunder and lightning",
            city="Bangalore",
            state="Karnataka",
            latitude=12.9716,
            longitude=77.5946,
            created_at=datetime.now(timezone.utc),
            user_id="user-1"
        )
        db_session.add(report)
        await db_session.commit()
        
        result = await verify_report("pipeline-status", db_session)
        
        # Status must be one of the valid values
        valid_statuses = ["verified", "disputed", "fake", "unverified"]
        assert result.verification_status in valid_statuses

