"""
Tests for Reports API endpoints.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.weather_report import WeatherReport
from tests.conftest import WeatherReportTest


# Override database dependency for API tests
@pytest.fixture
def override_get_db(db_session):
    """Override get_db dependency to use test database."""
    async def _get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


class TestSubmitReport:
    """Test POST /api/reports/submit endpoint."""
    
    @pytest.mark.asyncio
    async def test_submit_valid_report(self, db_session, override_get_db):
        """Test submitting a valid weather report."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "flooding",
                    "description": "Heavy waterlogging near Marine Drive, vehicles stranded in water",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "gps": {"lat": 18.9432, "lon": 72.8234}
                }
            )
        
        assert response.status_code == 201
        data = response.json()
        
        assert "report_id" in data
        assert data["status"] == "pending"
        assert "successfully" in data["message"].lower()
        
        # Verify report was created in database
        report_id = data["report_id"]
        query = select(WeatherReportTest).where(WeatherReportTest.id == report_id)
        result = await db_session.execute(query)
        report = result.scalar_one_or_none()
        
        assert report is not None
        assert report.event_type == "flooding"
        assert report.city == "Mumbai"
        assert report.state == "Maharashtra"
        assert report.source_type == "citizen_form"
    
    @pytest.mark.asyncio
    async def test_submit_report_without_gps(self, db_session, override_get_db):
        """Test submitting a report without GPS coordinates."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "rainfall",
                    "description": "Heavy rainfall observed throughout the day",
                    "city": "Delhi",
                    "state": "Delhi"
                }
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "report_id" in data
    
    @pytest.mark.asyncio
    async def test_submit_report_validation_errors(self, db_session, override_get_db):
        """Test validation errors for invalid input."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Missing required field (description)
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "flooding",
                    "city": "Mumbai",
                    "state": "Maharashtra"
                }
            )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_submit_report_invalid_event_type(self, db_session, override_get_db):
        """Test submitting report with invalid event type."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "invalid_event",
                    "description": "Some weather event",
                    "city": "Mumbai",
                    "state": "Maharashtra"
                }
            )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_submit_report_description_too_short(self, db_session, override_get_db):
        """Test submitting report with description too short."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "rainfall",
                    "description": "Rain",  # Too short
                    "city": "Mumbai",
                    "state": "Maharashtra"
                }
            )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_submit_report_description_too_long(self, db_session, override_get_db):
        """Test submitting report with description too long."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "rainfall",
                    "description": "A" * 501,  # Too long
                    "city": "Mumbai",
                    "state": "Maharashtra"
                }
            )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_submit_report_invalid_gps_coordinates(self, db_session, override_get_db):
        """Test submitting report with invalid GPS coordinates."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "flooding",
                    "description": "Heavy waterlogging near Marine Drive",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "gps": {"lat": 200, "lon": 300}  # Invalid coordinates
                }
            )
        
        assert response.status_code == 422  # Validation error


class TestGetReports:
    """Test GET /api/reports endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_reports_empty(self, db_session, override_get_db):
        """Test fetching reports when database is empty."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert data["reports"] == []
        assert data["limit"] == 100
        assert data["offset"] == 0
    
    @pytest.mark.asyncio
    async def test_get_reports_with_data(self, db_session, override_get_db):
        """Test fetching reports with some data in database."""
        # Create test reports
        report1 = WeatherReportTest(
            id="report-1",
            source_type="citizen_form",
            raw_text="Heavy rainfall",
            event_type="rainfall",
            city="Mumbai",
            state="Maharashtra",
            verification_status="verified",
            confidence_score=0.85,
            created_at=datetime.now(timezone.utc)
        )
        report2 = WeatherReportTest(
            id="report-2",
            source_type="citizen_form",
            raw_text="Flooding in streets",
            event_type="flooding",
            city="Chennai",
            state="Tamil Nadu",
            verification_status="disputed",
            confidence_score=0.55,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(report1)
        db_session.add(report2)
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 2
        assert len(data["reports"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_reports_filter_by_event_type(self, db_session, override_get_db):
        """Test filtering reports by event type."""
        # Create test reports
        report1 = WeatherReportTest(
            id="report-event-1",
            source_type="citizen_form",
            raw_text="Heavy rainfall",
            event_type="rainfall",
            city="Mumbai",
            state="Maharashtra",
            created_at=datetime.now(timezone.utc)
        )
        report2 = WeatherReportTest(
            id="report-event-2",
            source_type="citizen_form",
            raw_text="Flooding",
            event_type="flooding",
            city="Mumbai",
            state="Maharashtra",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(report1)
        db_session.add(report2)
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports?event_type=rainfall")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert data["reports"][0]["event_type"] == "rainfall"
    
    @pytest.mark.asyncio
    async def test_get_reports_filter_by_multiple_event_types(self, db_session, override_get_db):
        """Test filtering reports by multiple event types (comma-separated)."""
        # Create test reports
        report1 = WeatherReportTest(
            id="report-multi-1",
            source_type="citizen_form",
            raw_text="Heavy rainfall",
            event_type="rainfall",
            city="Mumbai",
            state="Maharashtra",
            created_at=datetime.now(timezone.utc)
        )
        report2 = WeatherReportTest(
            id="report-multi-2",
            source_type="citizen_form",
            raw_text="Flooding",
            event_type="flooding",
            city="Mumbai",
            state="Maharashtra",
            created_at=datetime.now(timezone.utc)
        )
        report3 = WeatherReportTest(
            id="report-multi-3",
            source_type="citizen_form",
            raw_text="Heatwave",
            event_type="heatwave",
            city="Delhi",
            state="Delhi",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add_all([report1, report2, report3])
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports?event_type=rainfall,flooding")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 2
        event_types = [r["event_type"] for r in data["reports"]]
        assert "rainfall" in event_types
        assert "flooding" in event_types
        assert "heatwave" not in event_types
    
    @pytest.mark.asyncio
    async def test_get_reports_filter_by_state(self, db_session, override_get_db):
        """Test filtering reports by state."""
        report1 = WeatherReportTest(
            id="report-state-1",
            source_type="citizen_form",
            raw_text="Heavy rainfall",
            event_type="rainfall",
            city="Mumbai",
            state="Maharashtra",
            created_at=datetime.now(timezone.utc)
        )
        report2 = WeatherReportTest(
            id="report-state-2",
            source_type="citizen_form",
            raw_text="Heatwave",
            event_type="heatwave",
            city="Delhi",
            state="Delhi",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add_all([report1, report2])
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports?state=Maharashtra")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert data["reports"][0]["location"]["state"] == "Maharashtra"
    
    @pytest.mark.asyncio
    async def test_get_reports_filter_by_verification_status(self, db_session, override_get_db):
        """Test filtering reports by verification status."""
        report1 = WeatherReportTest(
            id="report-status-1",
            source_type="citizen_form",
            raw_text="Verified report",
            event_type="rainfall",
            city="Mumbai",
            state="Maharashtra",
            verification_status="verified",
            confidence_score=0.85,
            created_at=datetime.now(timezone.utc)
        )
        report2 = WeatherReportTest(
            id="report-status-2",
            source_type="citizen_form",
            raw_text="Fake report",
            event_type="flooding",
            city="Mumbai",
            state="Maharashtra",
            verification_status="fake",
            confidence_score=0.2,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add_all([report1, report2])
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports?status=verified")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert data["reports"][0]["verification_status"] == "verified"
    
    @pytest.mark.asyncio
    async def test_get_reports_filter_by_date_range(self, db_session, override_get_db):
        """Test filtering reports by date range."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        report1 = WeatherReportTest(
            id="report-date-1",
            source_type="citizen_form",
            raw_text="Recent report",
            event_type="rainfall",
            city="Mumbai",
            state="Maharashtra",
            created_at=now
        )
        report2 = WeatherReportTest(
            id="report-date-2",
            source_type="citizen_form",
            raw_text="Old report",
            event_type="flooding",
            city="Mumbai",
            state="Maharashtra",
            created_at=two_days_ago
        )
        db_session.add_all([report1, report2])
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/reports?date_from={yesterday.isoformat()}"
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only get the recent report
        assert data["total"] == 1
    
    @pytest.mark.asyncio
    async def test_get_reports_pagination(self, db_session, override_get_db):
        """Test pagination with limit and offset."""
        # Create 5 reports
        for i in range(5):
            report = WeatherReportTest(
                id=f"report-page-{i}",
                source_type="citizen_form",
                raw_text=f"Report {i}",
                event_type="rainfall",
                city="Mumbai",
                state="Maharashtra",
                created_at=datetime.now(timezone.utc)
            )
            db_session.add(report)
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Get first 2 reports
            response1 = await client.get("/api/reports?limit=2&offset=0")
            data1 = response1.json()
            
            assert data1["total"] == 5
            assert len(data1["reports"]) == 2
            assert data1["limit"] == 2
            assert data1["offset"] == 0
            
            # Get next 2 reports
            response2 = await client.get("/api/reports?limit=2&offset=2")
            data2 = response2.json()
            
            assert data2["total"] == 5
            assert len(data2["reports"]) == 2
            assert data2["offset"] == 2


class TestGetReportById:
    """Test GET /api/reports/{id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_report_by_id_success(self, db_session, override_get_db):
        """Test fetching a specific report by ID."""
        report = WeatherReportTest(
            id="report-detail-1",
            source_type="citizen_form",
            raw_text="Detailed report description",
            event_type="flooding",
            city="Mumbai",
            state="Maharashtra",
            verification_status="verified",
            confidence_score=0.85,
            signals=json.dumps({"ground_truth": {"confidence": 0.8}}),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(report)
        await db_session.commit()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports/report-detail-1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == "report-detail-1"
        assert data["event_type"] == "flooding"
        assert data["verification_status"] == "verified"
        assert data["confidence_score"] == 0.85
        assert data["signals"] is not None
    
    @pytest.mark.asyncio
    async def test_get_report_by_id_not_found(self, db_session, override_get_db):
        """Test fetching a non-existent report."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports/00000000-0000-0000-0000-000000000000")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestEndToEndReportFlow:
    """Test complete flow: submit → verify → retrieve."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_report_flow(self, db_session, override_get_db):
        """Test complete report lifecycle."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Step 1: Submit a report
            submit_response = await client.post(
                "/api/reports/submit",
                json={
                    "event_type": "rainfall",
                    "description": "Heavy rainfall with thunderstorms throughout the evening",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "gps": {"lat": 12.9716, "lon": 77.5946}
                }
            )
            
            assert submit_response.status_code == 201
            report_id = submit_response.json()["report_id"]
            
            # Step 2: Fetch the report by ID
            detail_response = await client.get(f"/api/reports/{report_id}")
            assert detail_response.status_code == 200
            detail_data = detail_response.json()
            
            assert detail_data["id"] == report_id
            assert detail_data["event_type"] == "rainfall"
            
            # Step 3: Fetch from list endpoint
            list_response = await client.get("/api/reports?event_type=rainfall")
            assert list_response.status_code == 200
            list_data = list_response.json()
            
            assert list_data["total"] >= 1
            report_ids = [r["id"] for r in list_data["reports"]]
            assert report_id in report_ids


