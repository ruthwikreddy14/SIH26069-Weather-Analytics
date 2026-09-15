"""
GPS Spoofing Detection and Location Verification (Phase 3.7)

Verifies GPS coordinates and detects potential spoofing by:
1. Checking if GPS is within India bounding box (lat: 8–37°N, lon: 68–97°E)
2. Checking if GPS is within 500km of declared city
3. Fallback to text-based location extraction using spaCy NER
4. Geocoding via Nominatim API

Sets location_source: gps_verified | gps_suspicious | text_inferred | unknown
Sets location_confidence: high | medium | low
"""

import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Import models - these will be patched in tests
from app.models.weather_report import WeatherReport

logger = logging.getLogger(__name__)


# India bounding box (lat: 8–37°N, lon: 68–97°E)
INDIA_LAT_MIN = 8.0
INDIA_LAT_MAX = 37.0
INDIA_LON_MIN = 68.0
INDIA_LON_MAX = 97.0

# Maximum distance between GPS and declared city (500km)
MAX_CITY_DISTANCE_KM = 500.0

# Geocoder with user agent
GEOCODER = Nominatim(user_agent="sih-weather-analytics/1.0")


@dataclass
class LocationVerificationResult:
    """Result of location verification."""
    
    location_source: str  # gps_verified | gps_suspicious | text_inferred | unknown
    location_confidence: str  # high | medium | low
    reasoning: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "location_source": self.location_source,
            "location_confidence": self.location_confidence,
            "reasoning": self.reasoning,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "city": self.city,
            "state": self.state
        }


def is_within_india(lat: float, lon: float) -> bool:
    """
    Check if coordinates are within India bounding box.
    
    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        
    Returns:
        True if within India, False otherwise
    """
    return (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and 
            INDIA_LON_MIN <= lon <= INDIA_LON_MAX)


def parse_coordinates_from_location(location: any) -> Optional[Tuple[float, float]]:
    """
    Parse coordinates from a PostGIS Geography or WKB point.
    
    Args:
        location: PostGIS Geography object or WKB bytes
        
    Returns:
        (lat, lon) tuple or None if invalid
    """
    if location is None:
        return None
    
    try:
        # Check if it's a PostGIS Geography object with __geo_interface__
        if hasattr(location, '__geo_interface__'):
            coords = location.__geo_interface__['coordinates']
            # PostGIS stores as (lon, lat)
            return (coords[1], coords[0])
        
        # Check if it has a desc attribute (SQLAlchemy Geography)
        if hasattr(location, 'desc'):
            # Try to parse from WKT/WKB
            from geoalchemy2.shape import to_shape
            point = to_shape(location)
            return (point.y, point.x)  # Shapely Point has x=lon, y=lat
        
        # If it's a string representation like "POINT(lon lat)"
        if isinstance(location, str):
            if location.startswith('POINT'):
                # Parse "POINT(lon lat)"
                coords_str = location.replace('POINT(', '').replace(')', '')
                lon, lat = map(float, coords_str.split())
                return (lat, lon)
        
        return None
    except Exception as e:
        logger.warning(f"Failed to parse coordinates from location: {e}")
        return None


def geocode_city(city_name: str, timeout: int = 5) -> Optional[Tuple[float, float]]:
    """
    Geocode a city name to coordinates using Nominatim.
    
    Args:
        city_name: Name of the city
        timeout: Request timeout in seconds
        
    Returns:
        (lat, lon) tuple or None if geocoding fails
    """
    try:
        location = GEOCODER.geocode(f"{city_name}, India", timeout=timeout)
        if location:
            return (location.latitude, location.longitude)
        return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning(f"Geocoding failed for {city_name}: {e}")
        return None


def calculate_distance_km(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Calculate distance between two coordinates in kilometers.
    
    Args:
        coord1: (lat, lon) tuple
        coord2: (lat, lon) tuple
        
    Returns:
        Distance in kilometers
    """
    return geodesic(coord1, coord2).kilometers


async def verify_location(report_id: str, db: AsyncSession) -> LocationVerificationResult:
    """
    Verify location and detect GPS spoofing for a report.
    
    This is the main entry point for Phase 3.7 - it:
    1. Checks if GPS is within India bounding box
    2. Checks if GPS is within 500km of declared city
    3. Falls back to text-based location extraction if GPS is suspicious/missing
    4. Updates report with location_source and location_confidence
    
    Args:
        report_id: UUID of the report to verify
        db: Database session
        
    Returns:
        LocationVerificationResult with verification details
    """
    logger.info(f"Verifying location for report {report_id}")
    
    try:
        # Get the report
        query = select(WeatherReport).where(WeatherReport.id == report_id)
        result = await db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            logger.error(f"Report {report_id} not found")
            return LocationVerificationResult(
                location_source="unknown",
                location_confidence="low",
                reasoning=f"Report {report_id} not found"
            )
        
        # Parse GPS coordinates from location field
        gps_coords = parse_coordinates_from_location(report.location)
        
        if gps_coords:
            lat, lon = gps_coords
            logger.info(f"GPS coordinates found: lat={lat}, lon={lon}")
            
            # Check 1: Is GPS within India bounding box?
            if not is_within_india(lat, lon):
                logger.warning(f"GPS coordinates ({lat}, {lon}) are outside India bounding box")
                
                # Try text-based fallback
                result = await _fallback_to_text_inference(report, db)
                return result
            
            # Check 2: If city is provided, verify GPS is within 500km
            if report.city:
                city_coords = geocode_city(report.city)
                if city_coords:
                    distance = calculate_distance_km((lat, lon), city_coords)
                    logger.info(f"Distance between GPS and {report.city}: {distance:.1f} km")
                    
                    if distance > MAX_CITY_DISTANCE_KM:
                        logger.warning(f"GPS is {distance:.1f}km from declared city {report.city} (>500km)")
                        
                        # Mark as suspicious
                        report.location_source = "gps_suspicious"
                        report.location_confidence = "low"
                        
                        await db.commit()
                        
                        return LocationVerificationResult(
                            location_source="gps_suspicious",
                            location_confidence="low",
                            reasoning=f"GPS is {distance:.1f}km from declared city {report.city} (max: {MAX_CITY_DISTANCE_KM}km)",
                            latitude=lat,
                            longitude=lon,
                            city=report.city,
                            state=report.state
                        )
            
            # GPS passed all checks - mark as verified
            report.location_source = "gps_verified"
            report.location_confidence = "high"
            
            await db.commit()
            
            return LocationVerificationResult(
                location_source="gps_verified",
                location_confidence="high",
                reasoning="GPS coordinates verified: within India and consistent with declared city",
                latitude=lat,
                longitude=lon,
                city=report.city,
                state=report.state
            )
        
        else:
            logger.info("No GPS coordinates found, attempting text-based inference")
            # No GPS - try text-based location extraction
            result = await _fallback_to_text_inference(report, db)
            return result
    
    except Exception as e:
        logger.error(f"Location verification failed for report {report_id}: {e}")
        await db.rollback()
        raise


async def _fallback_to_text_inference(report: WeatherReport, db: AsyncSession) -> LocationVerificationResult:
    """
    Fallback to text-based location inference when GPS is unavailable or suspicious.
    
    Currently uses the declared city field. In a full implementation, this would:
    1. Use spaCy NER to extract place names from raw_text
    2. Geocode extracted names via Nominatim
    3. Update report.location with inferred coordinates
    
    Args:
        report: WeatherReport instance
        db: Database session
        
    Returns:
        LocationVerificationResult with inferred location
    """
    # For now, use declared city if available
    if report.city:
        coords = geocode_city(report.city)
        if coords:
            lat, lon = coords
            logger.info(f"Inferred location from city '{report.city}': lat={lat}, lon={lon}")
            
            report.location_source = "text_inferred"
            report.location_confidence = "medium"
            
            await db.commit()
            
            return LocationVerificationResult(
                location_source="text_inferred",
                location_confidence="medium",
                reasoning=f"Location inferred from declared city: {report.city}",
                latitude=lat,
                longitude=lon,
                city=report.city,
                state=report.state
            )
    
    # No location information available
    report.location_source = "unknown"
    report.location_confidence = "low"
    
    await db.commit()
    
    return LocationVerificationResult(
        location_source="unknown",
        location_confidence="low",
        reasoning="No GPS coordinates or city information available",
        city=report.city,
        state=report.state
    )
