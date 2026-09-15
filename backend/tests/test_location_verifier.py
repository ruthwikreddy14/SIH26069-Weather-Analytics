"""
Tests for GPS spoofing detection and location verification (Phase 3.7).

Tests the verify_location function and location verification logic.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from app.ml.location_verifier import (
    verify_location,
    is_within_india,
    parse_coordinates_from_location,
    geocode_city,
    calculate_distance_km,
    LocationVerificationResult,
    INDIA_LAT_MIN,
    INDIA_LAT_MAX,
    INDIA_LON_MIN,
    INDIA_LON_MAX,
    MAX_CITY_DISTANCE_KM
)

# Use test models from conftest
from tests.conftest import (
    WeatherReportTest as WeatherReport
)


# ============================================================================
# Test: India Bounding Box Check
# ============================================================================

def test_is_within_india_mumbai():
    """Test that Mumbai coordinates are within India."""
    # Mumbai: ~19.07°N, 72.87°E
    assert is_within_india(19.07, 72.87) is True


def test_is_within_india_delhi():
    """Test that Delhi coordinates are within India."""
    # Delhi: ~28.61°N, 77.20°E
    assert is_within_india(28.61, 77.20) is True


def test_is_within_india_chennai():
    """Test that Chennai coordinates are within India."""
    # Chennai: ~13.08°N, 80.27°E
    assert is_within_india(13.08, 80.27) is True


def test_is_within_india_kashmir():
    """Test that Kashmir coordinates are within India."""
    # Kashmir: ~34°N, 75°E
    assert is_within_india(34.0, 75.0) is True


def test_is_within_india_kanyakumari():
    """Test that Kanyakumari (southernmost point) is within India."""
    # Kanyakumari: ~8.08°N, 77.54°E
    assert is_within_india(8.08, 77.54) is True


def test_is_within_india_outside_atlantic():
    """Test that Atlantic Ocean coordinates are outside India."""
    # Atlantic Ocean: 0°N, 0°E
    assert is_within_india(0.0, 0.0) is False


def test_is_within_india_outside_pacific():
    """Test that Pacific Ocean coordinates are outside India."""
    # Pacific: 20°N, 150°E
    assert is_within_india(20.0, 150.0) is False


def test_is_within_india_outside_europe():
    """Test that European coordinates are outside India."""
    # Paris: ~48.86°N, 2.35°E
    assert is_within_india(48.86, 2.35) is False


def test_is_within_india_outside_china():
    """Test that Chinese coordinates are outside India."""
    # Beijing: ~39.9°N, 116.4°E
    assert is_within_india(39.9, 116.4) is False


def test_is_within_india_boundary_cases():
    """Test exact boundary values."""
    # Minimum latitude (just inside)
    assert is_within_india(INDIA_LAT_MIN, 75.0) is True
    # Maximum latitude (just inside)
    assert is_within_india(INDIA_LAT_MAX, 75.0) is True
    # Minimum longitude (just inside)
    assert is_within_india(20.0, INDIA_LON_MIN) is True
    # Maximum longitude (just inside)
    assert is_within_india(20.0, INDIA_LON_MAX) is True
    
    # Just outside boundaries
    assert is_within_india(INDIA_LAT_MIN - 0.1, 75.0) is False
    assert is_within_india(INDIA_LAT_MAX + 0.1, 75.0) is False
    assert is_within_india(20.0, INDIA_LON_MIN - 0.1) is False
    assert is_within_india(20.0, INDIA_LON_MAX + 0.1) is False


# ============================================================================
# Test: Coordinate Parsing
# ============================================================================

def test_parse_coordinates_from_location_none():
    """Test parsing None location."""
    result = parse_coordinates_from_location(None)
    assert result is None


def test_parse_coordinates_from_location_string_point():
    """Test parsing string POINT format."""
    # PostGIS format: POINT(lon lat)
    location = "POINT(72.87 19.07)"
    result = parse_coordinates_from_location(location)
    assert result is not None
    lat, lon = result
    assert abs(lat - 19.07) < 0.01
    assert abs(lon - 72.87) < 0.01


def test_parse_coordinates_from_location_invalid_string():
    """Test parsing invalid location string."""
    result = parse_coordinates_from_location("invalid")
    assert result is None


# ============================================================================
# Test: Distance Calculation
# ============================================================================

def test_calculate_distance_same_point():
    """Test distance between same point is zero."""
    coord = (19.07, 72.87)  # Mumbai
    distance = calculate_distance_km(coord, coord)
    assert distance == 0.0


def test_calculate_distance_mumbai_delhi():
    """Test distance between Mumbai and Delhi (~1140km)."""
    mumbai = (19.07, 72.87)
    delhi = (28.61, 77.20)
    distance = calculate_distance_km(mumbai, delhi)
    # Should be around 1140km
    assert 1100 < distance < 1200


def test_calculate_distance_short():
    """Test short distance calculation."""
    coord1 = (19.0, 72.0)
    coord2 = (19.1, 72.1)  # ~15km apart
    distance = calculate_distance_km(coord1, coord2)
    assert 10 < distance < 20


# ============================================================================
# Test: Geocoding (with mocking)
# ============================================================================

@patch('app.ml.location_verifier.GEOCODER.geocode')
def test_geocode_city_success(mock_geocode):
    """Test successful city geocoding."""
    # Mock Nominatim response
    mock_location = Mock()
    mock_location.latitude = 19.07
    mock_location.longitude = 72.87
    mock_geocode.return_value = mock_location
    
    result = geocode_city("Mumbai")
    
    assert result is not None
    lat, lon = result
    assert lat == 19.07
    assert lon == 72.87
    mock_geocode.assert_called_once()


@patch('app.ml.location_verifier.GEOCODER.geocode')
def test_geocode_city_not_found(mock_geocode):
    """Test geocoding when city not found."""
    mock_geocode.return_value = None
    
    result = geocode_city("NonexistentCity123")
    
    assert result is None


@patch('app.ml.location_verifier.GEOCODER.geocode')
def test_geocode_city_timeout(mock_geocode):
    """Test geocoding with timeout error."""
    from geopy.exc import GeocoderTimedOut
    mock_geocode.side_effect = GeocoderTimedOut()
    
    result = geocode_city("Mumbai")
    
    assert result is None


# ============================================================================
# Test: Full Location Verification
# ============================================================================

@pytest.mark.asyncio
async def test_verify_location_gps_verified(db_session):
    """Test location verification with valid GPS within India."""
    # Create report with GPS in Mumbai
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall in Mumbai",
        event_type="flooding",
        location="POINT(72.87 19.07)",  # Mumbai coordinates
        city="Mumbai",
        state="Maharashtra",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Verify location
    result = await verify_location(str(report.id), db_session)
    
    # Should be verified
    assert result.location_source == "gps_verified"
    assert result.location_confidence == "high"
    assert "verified" in result.reasoning.lower()
    
    # Check report was updated
    await db_session.refresh(report)
    assert report.location_source == "gps_verified"
    assert report.location_confidence == "high"


@pytest.mark.asyncio
async def test_verify_location_gps_outside_india(db_session):
    """Test location verification with GPS outside India."""
    # Create report with GPS in Atlantic Ocean
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        location="POINT(0.0 0.0)",  # Atlantic Ocean
        city="Mumbai",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Mock geocoding for fallback
    with patch('app.ml.location_verifier.geocode_city') as mock_geocode:
        mock_geocode.return_value = (19.07, 72.87)  # Mumbai
        
        # Verify location
        result = await verify_location(str(report.id), db_session)
    
    # Should fall back to text inference
    assert result.location_source in ["text_inferred", "unknown"]
    assert "outside" in result.reasoning.lower() or "inferred" in result.reasoning.lower()


@pytest.mark.asyncio
@patch('app.ml.location_verifier.geocode_city')
async def test_verify_location_gps_far_from_city(mock_geocode, db_session):
    """Test location verification with GPS far from declared city."""
    # Mock Mumbai geocoding
    mock_geocode.return_value = (19.07, 72.87)
    
    # Create report with GPS in Delhi but declared city Mumbai
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Test report",
        event_type="flooding",
        location="POINT(77.20 28.61)",  # Delhi coordinates
        city="Mumbai",  # But claims Mumbai
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Verify location
    result = await verify_location(str(report.id), db_session)
    
    # Should be marked as suspicious (>500km from Mumbai)
    assert result.location_source == "gps_suspicious"
    assert result.location_confidence == "low"
    assert "km from declared city" in result.reasoning
    
    # Check report was updated
    await db_session.refresh(report)
    assert report.location_source == "gps_suspicious"
    assert report.location_confidence == "low"


@pytest.mark.asyncio
async def test_verify_location_no_gps(db_session):
    """Test location verification with no GPS coordinates."""
    # Create report without GPS
    report = WeatherReport(
        source_type="twitter",
        raw_text="Heavy rain reported",
        event_type="rainfall",
        location=None,
        city="Mumbai",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Mock geocoding
    with patch('app.ml.location_verifier.geocode_city') as mock_geocode:
        mock_geocode.return_value = (19.07, 72.87)
        
        # Verify location
        result = await verify_location(str(report.id), db_session)
    
    # Should use text inference
    assert result.location_source == "text_inferred"
    assert result.location_confidence == "medium"
    assert "inferred" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_verify_location_no_gps_no_city(db_session):
    """Test location verification with no GPS and no city."""
    # Create report without GPS or city
    report = WeatherReport(
        source_type="twitter",
        raw_text="Heavy rain somewhere",
        event_type="rainfall",
        location=None,
        city=None,
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Verify location
    result = await verify_location(str(report.id), db_session)
    
    # Should be unknown
    assert result.location_source == "unknown"
    assert result.location_confidence == "low"
    assert "no gps" in result.reasoning.lower() or "not available" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_verify_location_report_not_found(db_session):
    """Test location verification for non-existent report."""
    # Try to verify non-existent report
    result = await verify_location("00000000-0000-0000-0000-000000000000", db_session)
    
    assert result.location_source == "unknown"
    assert result.location_confidence == "low"
    assert "not found" in result.reasoning.lower()


# ============================================================================
# Test: LocationVerificationResult Serialization
# ============================================================================

def test_location_verification_result_to_dict():
    """Test LocationVerificationResult serialization."""
    result = LocationVerificationResult(
        location_source="gps_verified",
        location_confidence="high",
        reasoning="Test reasoning",
        latitude=19.07,
        longitude=72.87,
        city="Mumbai",
        state="Maharashtra"
    )
    
    result_dict = result.to_dict()
    
    assert result_dict["location_source"] == "gps_verified"
    assert result_dict["location_confidence"] == "high"
    assert result_dict["reasoning"] == "Test reasoning"
    assert result_dict["latitude"] == 19.07
    assert result_dict["longitude"] == 72.87
    assert result_dict["city"] == "Mumbai"
    assert result_dict["state"] == "Maharashtra"


# ============================================================================
# Test: Edge Cases
# ============================================================================

@pytest.mark.asyncio
@patch('app.ml.location_verifier.geocode_city')
async def test_verify_location_geocoding_fails(mock_geocode, db_session):
    """Test location verification when geocoding fails."""
    # Mock geocoding failure
    mock_geocode.return_value = None
    
    # Create report without GPS
    report = WeatherReport(
        source_type="twitter",
        raw_text="Heavy rain",
        event_type="rainfall",
        location=None,
        city="InvalidCity123",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Verify location
    result = await verify_location(str(report.id), db_session)
    
    # Should be unknown since geocoding failed
    assert result.location_source == "unknown"
    assert result.location_confidence == "low"


@pytest.mark.asyncio
@patch('app.ml.location_verifier.geocode_city')
async def test_verify_location_gps_close_to_city(mock_geocode, db_session):
    """Test location verification with GPS close to declared city."""
    # Mock Mumbai geocoding
    mock_geocode.return_value = (19.07, 72.87)
    
    # Create report with GPS near Mumbai (within 500km)
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall",
        event_type="flooding",
        location="POINT(72.90 19.10)",  # Very close to Mumbai
        city="Mumbai",
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Verify location
    result = await verify_location(str(report.id), db_session)
    
    # Should be verified (within 500km)
    assert result.location_source == "gps_verified"
    assert result.location_confidence == "high"


@pytest.mark.asyncio
async def test_verify_location_gps_no_city_declared(db_session):
    """Test location verification with GPS but no city declared."""
    # Create report with GPS but no city
    report = WeatherReport(
        source_type="citizen_form",
        raw_text="Heavy rainfall somewhere",
        event_type="flooding",
        location="POINT(72.87 19.07)",  # Mumbai coordinates
        city=None,
        reported_at=datetime.utcnow()
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    
    # Verify location
    result = await verify_location(str(report.id), db_session)
    
    # Should be verified (GPS within India, no city to check against)
    assert result.location_source == "gps_verified"
    assert result.location_confidence == "high"
