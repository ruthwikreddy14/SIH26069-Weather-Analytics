"""
AI-Powered Weather Event Clustering Service

Groups multiple weather reports that represent the same real-world weather event
based on geographic proximity, event type, temporal proximity, and text similarity.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from math import radians, cos, sin, asin, sqrt
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class WeatherEventCluster:
    """Represents a cluster of weather reports for the same event"""
    event_id: str
    event_type: str
    center_lat: float
    center_lon: float
    report_count: int
    report_ids: List[str]
    start_time: datetime
    end_time: datetime
    affected_radius_km: float
    avg_confidence_score: float
    verified_count: int
    disputed_count: int
    fake_count: int
    unverified_count: int
    dominant_status: str


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth in kilometers.
    
    Args:
        lat1, lon1: Coordinates of first point
        lat2, lon2: Coordinates of second point
    
    Returns:
        Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r


def calculate_centroid(coordinates: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate the geographic centroid of a set of coordinates.
    
    Args:
        coordinates: List of (lat, lon) tuples
    
    Returns:
        (center_lat, center_lon) tuple
    """
    if not coordinates:
        return (0.0, 0.0)
    
    total_lat = sum(lat for lat, _ in coordinates)
    total_lon = sum(lon for _, lon in coordinates)
    
    return (total_lat / len(coordinates), total_lon / len(coordinates))


def calculate_affected_radius(coordinates: List[Tuple[float, float]], 
                             center_lat: float, center_lon: float) -> float:
    """
    Calculate the maximum distance from center to any point in the cluster.
    
    Args:
        coordinates: List of (lat, lon) tuples
        center_lat, center_lon: Center coordinates
    
    Returns:
        Maximum radius in kilometers
    """
    if not coordinates:
        return 0.0
    
    max_distance = 0.0
    for lat, lon in coordinates:
        distance = haversine_distance(center_lat, center_lon, lat, lon)
        max_distance = max(max_distance, distance)
    
    return max_distance


class WeatherEventClusteringService:
    """
    Service for clustering weather reports into events.
    
    Clustering is based on:
    1. Geographic proximity (configurable radius)
    2. Same event type
    3. Temporal proximity (configurable time window)
    4. Text similarity (if available)
    """
    
    def __init__(self,
                 max_distance_km: float = 50.0,
                 max_time_window_hours: float = 24.0,
                 min_cluster_size: int = 2):
        """
        Initialize the clustering service.
        
        Args:
            max_distance_km: Maximum distance between reports to be clustered (km)
            max_time_window_hours: Maximum time difference between reports (hours)
            min_cluster_size: Minimum number of reports to form a cluster
        """
        self.max_distance_km = max_distance_km
        self.max_time_window_hours = max_time_window_hours
        self.min_cluster_size = min_cluster_size
        logger.info(f"WeatherEventClusteringService initialized: "
                   f"max_distance={max_distance_km}km, "
                   f"max_time={max_time_window_hours}h, "
                   f"min_size={min_cluster_size}")
    
    def cluster_reports(self, reports: List[Dict]) -> List[WeatherEventCluster]:
        """
        Cluster weather reports into events using DBSCAN-like approach.
        
        Args:
            reports: List of report dictionaries with required fields
        
        Returns:
            List of WeatherEventCluster objects
        """
        if not reports:
            logger.info("No reports provided for clustering")
            return []
        
        # Filter reports that have GPS coordinates and event type
        valid_reports = [
            r for r in reports 
            if (r.get('location') and 
                r['location'].get('lat') and 
                r['location'].get('lon') and
                r.get('event_type'))
        ]
        
        if len(valid_reports) < self.min_cluster_size:
            logger.info(f"Insufficient valid reports for clustering: {len(valid_reports)}")
            return []
        
        # Group reports by event type first
        reports_by_type = defaultdict(list)
        for report in valid_reports:
            reports_by_type[report['event_type']].append(report)
        
        all_clusters = []
        
        # Cluster each event type separately
        for event_type, type_reports in reports_by_type.items():
            if len(type_reports) < self.min_cluster_size:
                continue
            
            # Sort by timestamp for temporal clustering
            sorted_reports = sorted(type_reports, key=lambda r: r['reported_at'])
            
            # Find clusters using greedy approach
            clusters = self._find_clusters(sorted_reports, event_type)
            all_clusters.extend(clusters)
        
        logger.info(f"Clustered {len(valid_reports)} reports into {len(all_clusters)} events")
        return all_clusters
    
    def _find_clusters(self, reports: List[Dict], event_type: str) -> List[WeatherEventCluster]:
        """
        Find clusters within reports of the same event type.
        
        Uses a greedy algorithm:
        1. Start with first unclustered report
        2. Find all nearby reports within distance and time thresholds
        3. Form cluster if enough reports found
        4. Repeat with next unclustered report
        """
        clusters = []
        clustered_indices = set()
        
        for i, seed_report in enumerate(reports):
            if i in clustered_indices:
                continue
            
            # Find all reports near this seed
            cluster_indices = self._find_nearby_reports(i, reports, clustered_indices)
            
            if len(cluster_indices) >= self.min_cluster_size:
                # Create cluster
                cluster = self._create_cluster(
                    [reports[idx] for idx in cluster_indices],
                    event_type
                )
                clusters.append(cluster)
                clustered_indices.update(cluster_indices)
        
        return clusters
    
    def _find_nearby_reports(self, seed_idx: int, reports: List[Dict], 
                            excluded: set) -> List[int]:
        """
        Find all reports near the seed report.
        
        Args:
            seed_idx: Index of seed report
            reports: All reports
            excluded: Set of already clustered indices
        
        Returns:
            List of indices forming a cluster
        """
        seed = reports[seed_idx]
        seed_lat = seed['location']['lat']
        seed_lon = seed['location']['lon']
        seed_time = seed['reported_at']
        
        if isinstance(seed_time, str):
            seed_time = datetime.fromisoformat(seed_time.replace('Z', '+00:00'))
        
        cluster = [seed_idx]
        
        for i, report in enumerate(reports):
            if i == seed_idx or i in excluded:
                continue
            
            # Check geographic proximity
            report_lat = report['location']['lat']
            report_lon = report['location']['lon']
            distance = haversine_distance(seed_lat, seed_lon, report_lat, report_lon)
            
            if distance > self.max_distance_km:
                continue
            
            # Check temporal proximity
            report_time = report['reported_at']
            if isinstance(report_time, str):
                report_time = datetime.fromisoformat(report_time.replace('Z', '+00:00'))
            
            time_diff = abs((report_time - seed_time).total_seconds() / 3600)
            
            if time_diff > self.max_time_window_hours:
                continue
            
            # Report is nearby in space and time
            cluster.append(i)
        
        return cluster
    
    def _create_cluster(self, reports: List[Dict], event_type: str) -> WeatherEventCluster:
        """
        Create a WeatherEventCluster from a list of reports.
        
        Args:
            reports: List of report dictionaries
            event_type: Common event type
        
        Returns:
            WeatherEventCluster object
        """
        # Extract coordinates
        coordinates = [
            (r['location']['lat'], r['location']['lon'])
            for r in reports
        ]
        
        # Calculate centroid
        center_lat, center_lon = calculate_centroid(coordinates)
        
        # Calculate affected radius
        affected_radius = calculate_affected_radius(coordinates, center_lat, center_lon)
        
        # Extract timestamps
        timestamps = []
        for r in reports:
            ts = r['reported_at']
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            timestamps.append(ts)
        
        start_time = min(timestamps)
        end_time = max(timestamps)
        
        # Calculate statistics
        verified_count = sum(1 for r in reports if r.get('verification_status') == 'verified')
        disputed_count = sum(1 for r in reports if r.get('verification_status') == 'disputed')
        fake_count = sum(1 for r in reports if r.get('verification_status') == 'fake')
        unverified_count = sum(1 for r in reports if not r.get('verification_status') or 
                                 r.get('verification_status') == 'unverified')
        
        # Determine dominant status
        status_counts = {
            'verified': verified_count,
            'disputed': disputed_count,
            'fake': fake_count,
            'unverified': unverified_count
        }
        dominant_status = max(status_counts.items(), key=lambda x: x[1])[0]
        
        # Calculate average confidence
        confidences = [r.get('confidence_score', 0.0) for r in reports if r.get('confidence_score') is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Generate event ID
        event_id = f"EVENT_{event_type}_{start_time.strftime('%Y%m%d%H%M')}_{len(reports)}"
        
        return WeatherEventCluster(
            event_id=event_id,
            event_type=event_type,
            center_lat=center_lat,
            center_lon=center_lon,
            report_count=len(reports),
            report_ids=[r['id'] for r in reports],
            start_time=start_time,
            end_time=end_time,
            affected_radius_km=round(affected_radius, 2),
            avg_confidence_score=round(avg_confidence, 4),
            verified_count=verified_count,
            disputed_count=disputed_count,
            fake_count=fake_count,
            unverified_count=unverified_count,
            dominant_status=dominant_status
        )


def get_clustering_service() -> WeatherEventClusteringService:
    """
    Get singleton instance of clustering service.
    
    Returns:
        WeatherEventClusteringService instance
    """
    return WeatherEventClusteringService(
        max_distance_km=50.0,    # 50km radius
        max_time_window_hours=24.0,  # 24 hour window
        min_cluster_size=2       # At least 2 reports to form event
    )
