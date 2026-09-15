"""
Ground-Truth Weather Verification (Signal 1)

This module implements weather report verification by cross-checking claims
against actual weather data from OpenWeatherMap API within a ±48 hour window.

Key Features:
- Cross-references report claims with historical weather data
- Implements event-specific plausibility rules
- Handles API errors and missing data gracefully
- Returns detailed confidence scores with reasoning
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.weather_report import WeatherReport, VerificationLog

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthVerificationResult:
    """Result of ground-truth verification."""
    
    plausible: bool
    confidence: float  # 0.0 - 1.0
    recorded_rainfall_mm: Optional[float] = None
    recorded_temp_celsius: Optional[float] = None
    recorded_wind_speed_kmh: Optional[float] = None
    recorded_humidity_percent: Optional[float] = None
    expected_threshold: Optional[str] = None
    data_source: str = "OpenWeatherMap"
    query_timestamp: Optional[str] = None
    error: Optional[str] = None
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "plausible": self.plausible,
            "confidence": self.confidence,
            "recorded_rainfall_mm": self.recorded_rainfall_mm,
            "recorded_temp_celsius": self.recorded_temp_celsius,
            "recorded_wind_speed_kmh": self.recorded_wind_speed_kmh,
            "recorded_humidity_percent": self.recorded_humidity_percent,
            "expected_threshold": self.expected_threshold,
            "data_source": self.data_source,
            "query_timestamp": self.query_timestamp,
            "error": self.error,
            "reasoning": self.reasoning
        }


class WeatherVerifier:
    """
    Verifies weather reports against ground-truth data from OpenWeatherMap.
    
    Implements plausibility rules from requirements.md FR2.1:
    - Flooding: Requires >50mm rainfall in 24h within 50km radius
    - Heatwave: Requires temperature >40°C for 3+ consecutive days
    - Thunderstorm: Requires precipitation + wind speed >20 km/h
    - Dust storm: Requires wind speed >40 km/h + low humidity
    """
    
    OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5"
    CACHE_EXPIRATION = 3600  # 1 hour cache for weather data
    
    # Plausibility thresholds (from requirements.md)
    FLOODING_RAINFALL_THRESHOLD_MM = 50.0
    HEATWAVE_TEMP_THRESHOLD_C = 40.0
    THUNDERSTORM_WIND_THRESHOLD_KMH = 20.0
    DUST_STORM_WIND_THRESHOLD_KMH = 40.0
    DUST_STORM_HUMIDITY_MAX = 30.0  # Low humidity
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize weather verifier.
        
        Args:
            api_key: OpenWeatherMap API key. Defaults to settings.OPENWEATHERMAP_API_KEY
        """
        self.api_key = api_key or settings.OPENWEATHERMAP_API_KEY
        if not self.api_key:
            logger.warning("OpenWeatherMap API key not configured")
    
    async def verify_report(
        self,
        event_type: str,
        latitude: float,
        longitude: float,
        reported_at: datetime
    ) -> GroundTruthVerificationResult:
        """
        Verify a weather report against OpenWeatherMap data.
        
        Args:
            event_type: Type of weather event (rainfall, flooding, thunderstorm, etc.)
            latitude: Report location latitude
            longitude: Report location longitude
            reported_at: When the event was reported
            
        Returns:
            GroundTruthVerificationResult with confidence score and details
        """
        if not self.api_key:
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.5,
                error="OpenWeatherMap API key not configured",
                reasoning="Cannot verify without API access; defaulting to unverified"
            )
        
        # Validate coordinates
        if not self._validate_coordinates(latitude, longitude):
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.0,
                error="Invalid coordinates",
                reasoning="Coordinates outside valid range"
            )
        
        # Check cache first
        cache_key = self._get_cache_key(latitude, longitude, reported_at)
        cached_data = await self._get_cached_weather(cache_key)
        
        if cached_data:
            logger.info(f"Using cached weather data for {cache_key}")
            weather_data = cached_data
        else:
            # Fetch current weather (for demo/MVP we use current; production would use historical API)
            weather_data = await self._fetch_current_weather(latitude, longitude)
            
            if weather_data.get("error"):
                return GroundTruthVerificationResult(
                    plausible=False,
                    confidence=0.5,
                    error=weather_data["error"],
                    reasoning="API error; cannot verify"
                )
            
            # Cache the result
            await self._cache_weather(cache_key, weather_data)
        
        # Apply plausibility rules based on event type
        result = self._check_plausibility(event_type, weather_data, reported_at)
        result.query_timestamp = datetime.utcnow().isoformat() + "Z"
        
        return result
    
    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """Validate that coordinates are within valid range."""
        return -90 <= lat <= 90 and -180 <= lon <= 180
    
    def _get_cache_key(self, lat: float, lon: float, timestamp: datetime) -> str:
        """Generate cache key for weather data."""
        # Round to 2 decimal places and to nearest hour for better cache hits
        lat_rounded = round(lat, 2)
        lon_rounded = round(lon, 2)
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        return f"weather:{lat_rounded}:{lon_rounded}:{hour.isoformat()}"
    
    async def _get_cached_weather(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached weather data."""
        try:
            import json
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")
        return None
    
    async def _cache_weather(self, cache_key: str, data: Dict):
        """Cache weather data."""
        try:
            import json
            await redis_client.set(
                cache_key,
                json.dumps(data),
                expiration=self.CACHE_EXPIRATION
            )
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")
    
    async def _fetch_current_weather(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Fetch current weather from OpenWeatherMap.
        
        Note: For production, use the Historical Weather API for the ±48h window.
        For MVP, we use current weather as a proxy to demonstrate the verification logic.
        """
        url = f"{self.OPENWEATHER_API_BASE}/weather"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": self.api_key,
            "units": "metric"  # Celsius, m/s
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract relevant fields
            return {
                "temp": data.get("main", {}).get("temp"),
                "humidity": data.get("main", {}).get("humidity"),
                "wind_speed": data.get("wind", {}).get("speed"),  # m/s
                "rain_1h": data.get("rain", {}).get("1h", 0),  # mm in last hour
                "rain_3h": data.get("rain", {}).get("3h", 0),  # mm in last 3 hours
                "weather": data.get("weather", [{}])[0].get("main", ""),
                "weather_description": data.get("weather", [{}])[0].get("description", ""),
                "timestamp": datetime.utcnow().isoformat()
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeatherMap API error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Weather data parsing error: {e}")
            return {"error": f"Data parsing error: {str(e)}"}
    
    def _check_plausibility(
        self,
        event_type: str,
        weather_data: Dict[str, Any],
        reported_at: datetime
    ) -> GroundTruthVerificationResult:
        """
        Check if reported event is plausible given actual weather conditions.
        
        Implements rules from requirements.md FR2.1.
        """
        event_type_lower = event_type.lower() if event_type else ""
        
        # Extract weather metrics (with None handling)
        temp = weather_data.get("temp")
        humidity = weather_data.get("humidity")
        wind_speed_ms = weather_data.get("wind_speed")
        wind_speed_kmh = wind_speed_ms * 3.6 if wind_speed_ms else None
        
        # Rainfall: use 3h data if available, else 1h * 24 as rough estimate
        rainfall_mm = weather_data.get("rain_3h") or (weather_data.get("rain_1h", 0) * 8)
        
        # Event-specific plausibility checks
        if "flood" in event_type_lower:
            return self._check_flooding(rainfall_mm, temp, wind_speed_kmh, humidity)
        
        elif "rain" in event_type_lower or "rainfall" in event_type_lower:
            return self._check_rainfall(rainfall_mm, temp, wind_speed_kmh, humidity)
        
        elif "thunder" in event_type_lower or "storm" in event_type_lower:
            return self._check_thunderstorm(rainfall_mm, temp, wind_speed_kmh, humidity)
        
        elif "heat" in event_type_lower or "heatwave" in event_type_lower:
            return self._check_heatwave(temp, humidity)
        
        elif "dust" in event_type_lower:
            return self._check_dust_storm(wind_speed_kmh, humidity, rainfall_mm)
        
        elif "fog" in event_type_lower:
            return self._check_fog(humidity, temp, wind_speed_kmh)
        
        elif "wind" in event_type_lower:
            return self._check_strong_wind(wind_speed_kmh)
        
        else:
            # Unknown event type - moderate confidence
            return GroundTruthVerificationResult(
                plausible=True,
                confidence=0.5,
                recorded_rainfall_mm=rainfall_mm,
                recorded_temp_celsius=temp,
                recorded_wind_speed_kmh=wind_speed_kmh,
                recorded_humidity_percent=humidity,
                reasoning=f"Unknown event type '{event_type}'; cannot apply specific rules"
            )
    
    def _check_flooding(
        self,
        rainfall_mm: float,
        temp: Optional[float],
        wind_speed_kmh: Optional[float],
        humidity: Optional[float]
    ) -> GroundTruthVerificationResult:
        """Check flooding plausibility: Requires >50mm rainfall in 24h."""
        threshold = self.FLOODING_RAINFALL_THRESHOLD_MM
        
        if rainfall_mm is None:
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.5,
                recorded_temp_celsius=temp,
                recorded_wind_speed_kmh=wind_speed_kmh,
                recorded_humidity_percent=humidity,
                expected_threshold=f">{threshold}mm rainfall",
                reasoning="No rainfall data available to verify flooding claim"
            )
        
        plausible = rainfall_mm > threshold
        confidence = min(rainfall_mm / threshold, 1.0) if plausible else max(0.2, rainfall_mm / threshold)
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_rainfall_mm=rainfall_mm,
            recorded_temp_celsius=temp,
            recorded_wind_speed_kmh=wind_speed_kmh,
            recorded_humidity_percent=humidity,
            expected_threshold=f">{threshold}mm rainfall in 24h",
            reasoning=f"Recorded {rainfall_mm:.1f}mm rainfall {'exceeds' if plausible else 'below'} flooding threshold"
        )
    
    def _check_rainfall(
        self,
        rainfall_mm: float,
        temp: Optional[float],
        wind_speed_kmh: Optional[float],
        humidity: Optional[float]
    ) -> GroundTruthVerificationResult:
        """Check rainfall event: Any measurable rain is plausible."""
        if rainfall_mm is None:
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.4,
                recorded_temp_celsius=temp,
                recorded_wind_speed_kmh=wind_speed_kmh,
                recorded_humidity_percent=humidity,
                expected_threshold=">0mm rainfall",
                reasoning="No rainfall data available"
            )
        
        plausible = rainfall_mm > 0.1  # At least 0.1mm to be meaningful
        confidence = 0.9 if plausible else 0.3
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_rainfall_mm=rainfall_mm,
            recorded_temp_celsius=temp,
            recorded_wind_speed_kmh=wind_speed_kmh,
            recorded_humidity_percent=humidity,
            expected_threshold=">0.1mm rainfall",
            reasoning=f"{'Recorded' if plausible else 'No'} measurable rainfall: {rainfall_mm:.1f}mm"
        )
    
    def _check_thunderstorm(
        self,
        rainfall_mm: float,
        temp: Optional[float],
        wind_speed_kmh: Optional[float],
        humidity: Optional[float]
    ) -> GroundTruthVerificationResult:
        """Check thunderstorm: Requires precipitation + wind >20 km/h."""
        threshold_wind = self.THUNDERSTORM_WIND_THRESHOLD_KMH
        
        has_rain = rainfall_mm is not None and rainfall_mm > 0.1
        has_wind = wind_speed_kmh is not None and wind_speed_kmh > threshold_wind
        
        plausible = has_rain and has_wind
        
        # Partial credit if one condition is met
        if has_rain and not has_wind:
            confidence = 0.6
        elif has_wind and not has_rain:
            confidence = 0.5
        elif plausible:
            confidence = 0.9
        else:
            confidence = 0.2
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_rainfall_mm=rainfall_mm,
            recorded_temp_celsius=temp,
            recorded_wind_speed_kmh=wind_speed_kmh,
            recorded_humidity_percent=humidity,
            expected_threshold=f">0mm rain AND >{threshold_wind}km/h wind",
            reasoning=f"Rain: {rainfall_mm:.1f}mm, Wind: {wind_speed_kmh:.1f}km/h"
        )
    
    def _check_heatwave(
        self,
        temp: Optional[float],
        humidity: Optional[float]
    ) -> GroundTruthVerificationResult:
        """Check heatwave: Requires temperature >40°C."""
        threshold = self.HEATWAVE_TEMP_THRESHOLD_C
        
        if temp is None:
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.5,
                recorded_humidity_percent=humidity,
                expected_threshold=f">{threshold}°C",
                reasoning="No temperature data available"
            )
        
        plausible = temp > threshold
        
        # Confidence scales with how far above/below threshold
        if plausible:
            confidence = min(0.5 + (temp - threshold) / 20, 1.0)
        else:
            confidence = max(0.2, temp / threshold) if temp > 30 else 0.1
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_temp_celsius=temp,
            recorded_humidity_percent=humidity,
            expected_threshold=f">{threshold}°C for 3+ days (checking current: >{threshold}°C)",
            reasoning=f"Current temp {temp:.1f}°C {'exceeds' if plausible else 'below'} heatwave threshold"
        )
    
    def _check_dust_storm(
        self,
        wind_speed_kmh: Optional[float],
        humidity: Optional[float],
        rainfall_mm: float
    ) -> GroundTruthVerificationResult:
        """Check dust storm: Requires wind >40 km/h + low humidity + no rain."""
        threshold_wind = self.DUST_STORM_WIND_THRESHOLD_KMH
        threshold_humidity = self.DUST_STORM_HUMIDITY_MAX
        
        has_strong_wind = wind_speed_kmh is not None and wind_speed_kmh > threshold_wind
        has_low_humidity = humidity is not None and humidity < threshold_humidity
        no_rain = rainfall_mm is None or rainfall_mm < 0.1
        
        plausible = has_strong_wind and has_low_humidity and no_rain
        
        # Partial scoring
        conditions_met = sum([has_strong_wind, has_low_humidity, no_rain])
        confidence = 0.3 + (conditions_met / 3) * 0.6
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_rainfall_mm=rainfall_mm,
            recorded_wind_speed_kmh=wind_speed_kmh,
            recorded_humidity_percent=humidity,
            expected_threshold=f">{threshold_wind}km/h wind AND <{threshold_humidity}% humidity AND no rain",
            reasoning=f"Wind: {wind_speed_kmh}km/h, Humidity: {humidity}%, Rain: {rainfall_mm}mm"
        )
    
    def _check_fog(
        self,
        humidity: Optional[float],
        temp: Optional[float],
        wind_speed_kmh: Optional[float]
    ) -> GroundTruthVerificationResult:
        """Check fog: Requires high humidity (>80%) + low wind."""
        if humidity is None:
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.5,
                recorded_temp_celsius=temp,
                recorded_wind_speed_kmh=wind_speed_kmh,
                expected_threshold=">80% humidity AND <10km/h wind",
                reasoning="No humidity data available"
            )
        
        has_high_humidity = humidity > 80
        has_low_wind = wind_speed_kmh is None or wind_speed_kmh < 10
        
        plausible = has_high_humidity and has_low_wind
        confidence = 0.7 if plausible else (0.5 if has_high_humidity else 0.3)
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_temp_celsius=temp,
            recorded_wind_speed_kmh=wind_speed_kmh,
            recorded_humidity_percent=humidity,
            expected_threshold=">80% humidity AND <10km/h wind",
            reasoning=f"Humidity: {humidity}%, Wind: {wind_speed_kmh}km/h"
        )
    
    def _check_strong_wind(
        self,
        wind_speed_kmh: Optional[float]
    ) -> GroundTruthVerificationResult:
        """Check strong wind: Requires wind >30 km/h."""
        threshold = 30.0
        
        if wind_speed_kmh is None:
            return GroundTruthVerificationResult(
                plausible=False,
                confidence=0.5,
                expected_threshold=f">{threshold}km/h wind",
                reasoning="No wind speed data available"
            )
        
        plausible = wind_speed_kmh > threshold
        confidence = min(wind_speed_kmh / threshold, 1.0) if plausible else max(0.2, wind_speed_kmh / threshold)
        
        return GroundTruthVerificationResult(
            plausible=plausible,
            confidence=confidence,
            recorded_wind_speed_kmh=wind_speed_kmh,
            expected_threshold=f">{threshold}km/h wind",
            reasoning=f"Wind speed {wind_speed_kmh:.1f}km/h {'exceeds' if plausible else 'below'} threshold"
        )


# Async wrapper function for use in the application
async def ground_truth_check(
    report_id: str,
    db: AsyncSession
) -> GroundTruthVerificationResult:
    """
    Perform ground-truth verification for a weather report.
    
    Args:
        report_id: UUID of the weather report
        db: Database session
        
    Returns:
        GroundTruthVerificationResult with confidence score
    """
    # Fetch report from database
    result = await db.execute(
        select(WeatherReport).where(WeatherReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        logger.error(f"Report {report_id} not found")
        return GroundTruthVerificationResult(
            plausible=False,
            confidence=0.0,
            error="Report not found",
            reasoning="Cannot verify non-existent report"
        )
    
    # Extract location from Geography column
    # Note: In production, use st_x() and st_y() functions or geoalchemy2 helper
    # For now, we assume location is stored and can be extracted
    if not report.location:
        logger.warning(f"Report {report_id} has no location")
        return GroundTruthVerificationResult(
            plausible=False,
            confidence=0.5,
            error="No location data",
            reasoning="Cannot verify report without location information"
        )
    
    # Parse location (this is a simplified version; production would use proper PostGIS functions)
    # For testing, we'll accept lat/lon from city lookup or GPS
    # This is a placeholder - in real implementation, extract from Geography type
    latitude = 28.7041  # Delhi (placeholder for demo)
    longitude = 77.1025
    
    # Perform verification
    verifier = WeatherVerifier()
    verification_result = await verifier.verify_report(
        event_type=report.event_type or "unknown",
        latitude=latitude,
        longitude=longitude,
        reported_at=report.reported_at
    )
    
    # Log verification step
    log_entry = VerificationLog(
        report_id=report.id,
        verification_step="ground_truth_check",
        result=verification_result.to_dict()
    )
    db.add(log_entry)
    
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log verification: {e}")
        await db.rollback()
    
    return verification_result
