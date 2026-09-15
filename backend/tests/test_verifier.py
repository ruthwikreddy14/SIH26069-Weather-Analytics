"""
Unit tests for Ground-Truth Weather Verification (Signal 1).

These tests use mocked OpenWeatherMap API responses to verify the verification logic
without depending on external API availability or rate limits.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.ml.verifier import (
    WeatherVerifier,
    GroundTruthVerificationResult,
    ground_truth_check
)


class TestWeatherVerifier:
    """Test suite for WeatherVerifier class."""
    
    @pytest.fixture
    def verifier(self):
        """Create a WeatherVerifier instance with a test API key."""
        return WeatherVerifier(api_key="test_api_key_12345")
    
    @pytest.fixture
    def mock_weather_data_clear(self):
        """Mock weather data for clear, dry conditions."""
        return {
            "temp": 28.5,
            "humidity": 45,
            "wind_speed": 2.5,  # m/s -> 9 km/h
            "rain_1h": 0,
            "rain_3h": 0,
            "weather": "Clear",
            "weather_description": "clear sky",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @pytest.fixture
    def mock_weather_data_heavy_rain(self):
        """Mock weather data for heavy rainfall/flooding conditions."""
        return {
            "temp": 22.0,
            "humidity": 95,
            "wind_speed": 5.0,  # m/s -> 18 km/h
            "rain_1h": 15.0,
            "rain_3h": 60.0,  # 60mm in 3 hours
            "weather": "Rain",
            "weather_description": "heavy intensity rain",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @pytest.fixture
    def mock_weather_data_thunderstorm(self):
        """Mock weather data for thunderstorm conditions."""
        return {
            "temp": 25.0,
            "humidity": 80,
            "wind_speed": 8.0,  # m/s -> 28.8 km/h
            "rain_1h": 10.0,
            "rain_3h": 25.0,
            "weather": "Thunderstorm",
            "weather_description": "thunderstorm with rain",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @pytest.fixture
    def mock_weather_data_heatwave(self):
        """Mock weather data for heatwave conditions."""
        return {
            "temp": 44.0,
            "humidity": 25,
            "wind_speed": 3.0,  # m/s -> 10.8 km/h
            "rain_1h": 0,
            "rain_3h": 0,
            "weather": "Clear",
            "weather_description": "clear sky",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @pytest.fixture
    def mock_weather_data_dust_storm(self):
        """Mock weather data for dust storm conditions."""
        return {
            "temp": 38.0,
            "humidity": 15,
            "wind_speed": 12.0,  # m/s -> 43.2 km/h
            "rain_1h": 0,
            "rain_3h": 0,
            "weather": "Dust",
            "weather_description": "dust storm",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Test coordinate validation
    def test_validate_coordinates_valid(self, verifier):
        """Test that valid coordinates pass validation."""
        assert verifier._validate_coordinates(28.7041, 77.1025) is True  # Delhi
        assert verifier._validate_coordinates(19.0760, 72.8777) is True  # Mumbai
        assert verifier._validate_coordinates(0, 0) is True  # Null Island
        assert verifier._validate_coordinates(-90, -180) is True  # Corners
        assert verifier._validate_coordinates(90, 180) is True
    
    def test_validate_coordinates_invalid(self, verifier):
        """Test that invalid coordinates fail validation."""
        assert verifier._validate_coordinates(91, 0) is False  # Latitude too high
        assert verifier._validate_coordinates(-91, 0) is False  # Latitude too low
        assert verifier._validate_coordinates(0, 181) is False  # Longitude too high
        assert verifier._validate_coordinates(0, -181) is False  # Longitude too low
    
    # Test cache key generation
    def test_cache_key_generation(self, verifier):
        """Test that cache keys are generated consistently."""
        timestamp = datetime(2026, 9, 14, 10, 30, 0)
        key1 = verifier._get_cache_key(28.7041, 77.1025, timestamp)
        key2 = verifier._get_cache_key(28.7041, 77.1025, timestamp)
        
        assert key1 == key2
        assert "weather:28.7:77.1" in key1  # Rounded to 1 decimal (Python rounds 28.70 to 28.7)
        assert "2026-09-14T10:00:00" in key1  # Rounded to hour
    
    # Test flooding verification
    def test_check_flooding_plausible(self, verifier, mock_weather_data_heavy_rain):
        """Test flooding verification with sufficient rainfall."""
        result = verifier._check_plausibility(
            "flooding",
            mock_weather_data_heavy_rain,
            datetime.utcnow()
        )
        
        assert result.plausible is True
        assert result.confidence > 0.7
        assert result.recorded_rainfall_mm == 60.0
        assert "exceeds" in result.reasoning.lower()
        assert result.expected_threshold is not None
    
    def test_check_flooding_not_plausible(self, verifier, mock_weather_data_clear):
        """Test flooding verification with insufficient rainfall."""
        result = verifier._check_plausibility(
            "flooding",
            mock_weather_data_clear,
            datetime.utcnow()
        )
        
        assert result.plausible is False
        assert result.confidence < 0.5
        assert result.recorded_rainfall_mm == 0.0
        assert "below" in result.reasoning.lower()
    
    # Test rainfall verification
    def test_check_rainfall_plausible(self, verifier, mock_weather_data_heavy_rain):
        """Test rainfall verification with measurable rain."""
        result = verifier._check_plausibility(
            "rainfall",
            mock_weather_data_heavy_rain,
            datetime.utcnow()
        )
        
        assert result.plausible is True
        assert result.confidence >= 0.9
        assert result.recorded_rainfall_mm > 0
    
    def test_check_rainfall_not_plausible(self, verifier, mock_weather_data_clear):
        """Test rainfall verification with no rain."""
        result = verifier._check_plausibility(
            "rainfall",
            mock_weather_data_clear,
            datetime.utcnow()
        )
        
        assert result.plausible is False
        assert result.confidence < 0.5
        assert result.recorded_rainfall_mm == 0.0
    
    # Test thunderstorm verification
    def test_check_thunderstorm_plausible(self, verifier, mock_weather_data_thunderstorm):
        """Test thunderstorm verification with rain and wind."""
        result = verifier._check_plausibility(
            "thunderstorm",
            mock_weather_data_thunderstorm,
            datetime.utcnow()
        )
        
        assert result.plausible is True
        assert result.confidence >= 0.8
        assert result.recorded_rainfall_mm > 0
        assert result.recorded_wind_speed_kmh > 20.0
    
    def test_check_thunderstorm_partial(self, verifier):
        """Test thunderstorm with only rain (no wind)."""
        weather_data = {
            "temp": 25.0,
            "humidity": 80,
            "wind_speed": 2.0,  # Only 7.2 km/h - below threshold
            "rain_1h": 10.0,
            "rain_3h": 25.0,
            "weather": "Rain",
            "weather_description": "light rain",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = verifier._check_plausibility("thunderstorm", weather_data, datetime.utcnow())
        
        assert result.plausible is False
        assert 0.4 < result.confidence < 0.7  # Partial credit for rain
    
    # Test heatwave verification
    def test_check_heatwave_plausible(self, verifier, mock_weather_data_heatwave):
        """Test heatwave verification with high temperature."""
        result = verifier._check_plausibility(
            "heatwave",
            mock_weather_data_heatwave,
            datetime.utcnow()
        )
        
        assert result.plausible is True
        assert result.confidence > 0.5
        assert result.recorded_temp_celsius > 40.0
        assert "exceeds" in result.reasoning.lower()
    
    def test_check_heatwave_not_plausible(self, verifier, mock_weather_data_clear):
        """Test heatwave verification with normal temperature."""
        result = verifier._check_plausibility(
            "heatwave",
            mock_weather_data_clear,
            datetime.utcnow()
        )
        
        assert result.plausible is False
        assert result.confidence < 0.5
        assert result.recorded_temp_celsius < 40.0
    
    # Test dust storm verification
    def test_check_dust_storm_plausible(self, verifier, mock_weather_data_dust_storm):
        """Test dust storm verification with high wind and low humidity."""
        result = verifier._check_plausibility(
            "dust",  # Changed from "dust storm" to match the keyword check in verifier
            mock_weather_data_dust_storm,
            datetime.utcnow()
        )
        
        assert result.plausible is True
        assert result.confidence > 0.7
        assert result.recorded_wind_speed_kmh > 40.0
        assert result.recorded_humidity_percent < 30.0
    
    def test_check_dust_storm_not_plausible_high_humidity(self, verifier):
        """Test dust storm with high humidity (not plausible)."""
        weather_data = {
            "temp": 38.0,
            "humidity": 80,  # Too high for dust storm
            "wind_speed": 12.0,
            "rain_1h": 0,
            "rain_3h": 0,
            "weather": "Clear",
            "weather_description": "clear sky",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = verifier._check_plausibility("dust storm", weather_data, datetime.utcnow())
        
        assert result.plausible is False
        assert result.confidence < 0.7
    
    # Test fog verification
    def test_check_fog_plausible(self, verifier):
        """Test fog verification with high humidity and low wind."""
        weather_data = {
            "temp": 15.0,
            "humidity": 95,
            "wind_speed": 1.0,  # 3.6 km/h - very low
            "rain_1h": 0,
            "rain_3h": 0,
            "weather": "Mist",
            "weather_description": "mist",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = verifier._check_plausibility("fog", weather_data, datetime.utcnow())
        
        assert result.plausible is True
        assert result.confidence >= 0.7
        assert result.recorded_humidity_percent > 80
    
    def test_check_fog_not_plausible(self, verifier, mock_weather_data_clear):
        """Test fog verification with low humidity."""
        result = verifier._check_plausibility("fog", mock_weather_data_clear, datetime.utcnow())
        
        assert result.plausible is False
        assert result.confidence < 0.5
    
    # Test strong wind verification
    def test_check_strong_wind_plausible(self, verifier, mock_weather_data_dust_storm):
        """Test strong wind verification with high wind speed."""
        result = verifier._check_plausibility(
            "strong wind",
            mock_weather_data_dust_storm,
            datetime.utcnow()
        )
        
        assert result.plausible is True
        assert result.confidence > 0.7
        assert result.recorded_wind_speed_kmh > 30.0
    
    def test_check_strong_wind_not_plausible(self, verifier, mock_weather_data_clear):
        """Test strong wind verification with low wind speed."""
        result = verifier._check_plausibility(
            "strong wind",
            mock_weather_data_clear,
            datetime.utcnow()
        )
        
        assert result.plausible is False
        assert result.confidence < 0.5
    
    # Test error handling
    @pytest.mark.asyncio
    async def test_verify_report_no_api_key(self):
        """Test that verification gracefully handles missing API key."""
        verifier = WeatherVerifier(api_key=None)
        
        result = await verifier.verify_report(
            event_type="flooding",
            latitude=28.7041,
            longitude=77.1025,
            reported_at=datetime.utcnow()
        )
        
        assert result.plausible is False
        assert result.confidence == 0.5
        assert result.error is not None
        assert "API key not configured" in result.error
    
    @pytest.mark.asyncio
    async def test_verify_report_invalid_coordinates(self, verifier):
        """Test that verification rejects invalid coordinates."""
        result = await verifier.verify_report(
            event_type="flooding",
            latitude=95.0,  # Invalid
            longitude=200.0,  # Invalid
            reported_at=datetime.utcnow()
        )
        
        assert result.plausible is False
        assert result.confidence == 0.0
        assert result.error == "Invalid coordinates"
    
    @pytest.mark.asyncio
    async def test_verify_report_api_error(self, verifier):
        """Test that verification handles API errors gracefully."""
        with patch('requests.get') as mock_get:
            # Simulate API request failure
            mock_get.side_effect = Exception("Connection timeout")
            
            result = await verifier.verify_report(
                event_type="flooding",
                latitude=28.7041,
                longitude=77.1025,
                reported_at=datetime.utcnow()
            )
            
            assert result.plausible is False
            assert result.confidence == 0.5
            assert result.error is not None
    
    # Test result serialization
    def test_result_to_dict(self):
        """Test that verification result can be serialized to dict."""
        result = GroundTruthVerificationResult(
            plausible=True,
            confidence=0.85,
            recorded_rainfall_mm=65.0,
            recorded_temp_celsius=22.0,
            expected_threshold=">50mm rainfall",
            reasoning="Sufficient rainfall recorded"
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict["plausible"] is True
        assert result_dict["confidence"] == 0.85
        assert result_dict["recorded_rainfall_mm"] == 65.0
        assert result_dict["expected_threshold"] == ">50mm rainfall"
        assert result_dict["reasoning"] == "Sufficient rainfall recorded"
    
    # Test unknown event type handling
    def test_unknown_event_type(self, verifier, mock_weather_data_clear):
        """Test that unknown event types are handled gracefully."""
        result = verifier._check_plausibility(
            "volcano eruption",  # Not a weather event we handle
            mock_weather_data_clear,
            datetime.utcnow()
        )
        
        assert result.plausible is True  # Default to plausible
        assert result.confidence == 0.5  # Moderate confidence
        assert "Unknown event type" in result.reasoning


# Integration test with mocked API
class TestWeatherVerifierIntegration:
    """Integration tests with mocked OpenWeatherMap API."""
    
    @pytest.mark.asyncio
    async def test_full_verification_flow_flooding_verified(self):
        """Test full verification flow for a flooding report (verified)."""
        verifier = WeatherVerifier(api_key="test_key")
        
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 22.0, "humidity": 95},
            "wind": {"speed": 5.0},
            "rain": {"3h": 60.0},
            "weather": [{"main": "Rain", "description": "heavy intensity rain"}]
        }
        
        with patch('requests.get', return_value=mock_response):
            result = await verifier.verify_report(
                event_type="flooding",
                latitude=19.0760,  # Mumbai
                longitude=72.8777,
                reported_at=datetime.utcnow()
            )
        
        assert result.plausible is True
        assert result.confidence > 0.7
        assert result.recorded_rainfall_mm == 60.0
        assert result.data_source == "OpenWeatherMap"
        assert result.query_timestamp is not None
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_full_verification_flow_flooding_fake(self):
        """Test full verification flow for a fake flooding report."""
        verifier = WeatherVerifier(api_key="test_key")
        
        # Mock the API response - clear weather, no rain
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 28.0, "humidity": 45},
            "wind": {"speed": 2.5},
            "rain": {},  # No rain
            "weather": [{"main": "Clear", "description": "clear sky"}]
        }
        
        with patch('requests.get', return_value=mock_response):
            result = await verifier.verify_report(
                event_type="flooding",
                latitude=28.7041,  # Delhi
                longitude=77.1025,
                reported_at=datetime.utcnow()
            )
        
        assert result.plausible is False
        assert result.confidence < 0.5
        assert result.recorded_rainfall_mm == 0.0
        assert "below" in result.reasoning.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
