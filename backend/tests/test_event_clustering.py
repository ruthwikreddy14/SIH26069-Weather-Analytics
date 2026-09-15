"""
Tests for Weather Event Clustering Service
"""

import pytest
from datetime import datetime, timedelta
from app.ml.event_clustering import (
    WeatherEventClusteringService,
    haversine_distance,
    calculate_centroid,
    calculate_affected_radius,
    get_clustering_service,
)


class TestHaversineDistance:
    """Test geographic distance calculations"""
    
    def test_same_location(self):
        """Distance between same point should be 0"""
        distance = haversine_distance(28.6139, 77.2090, 28.6139, 77.2090)
        assert distance == pytest.approx(0.0, abs=0.1)
    
    def test_delhi_mumbai_distance(self):
        """Test actual distance between Delhi and Mumbai"""
        # Delhi: 28.6139°N, 77.2090°E
        # Mumbai: 19.0760°N, 72.8777°E
        distance = haversine_distance(28.6139, 77.2090, 19.0760, 72.8777)
        # Actual distance is approximately 1150-1200 km
        assert 1100 < distance < 1250
    
    def test_short_distance(self):
        """Test short distance within a city"""
        # Two points about 14km apart
        distance = haversine_distance(28.6139, 77.2090, 28.7041, 77.1025)
        assert 13 < distance < 16


class TestCentroidCalculation:
    """Test geographic centroid calculations"""
    
    def test_single_point(self):
        """Centroid of single point is the point itself"""
        coords = [(28.6139, 77.2090)]
        center = calculate_centroid(coords)
        assert center == (28.6139, 77.2090)
    
    def test_two_points(self):
        """Centroid of two points is midpoint"""
        coords = [(0.0, 0.0), (10.0, 10.0)]
        center = calculate_centroid(coords)
        assert center == (5.0, 5.0)
    
    def test_empty_list(self):
        """Empty list returns (0, 0)"""
        coords = []
        center = calculate_centroid(coords)
        assert center == (0.0, 0.0)


class TestAffectedRadius:
    """Test affected radius calculations"""
    
    def test_single_point(self):
        """Radius with single point is 0"""
        coords = [(28.6139, 77.2090)]
        radius = calculate_affected_radius(coords, 28.6139, 77.2090)
        assert radius == pytest.approx(0.0, abs=0.1)
    
    def test_multiple_points(self):
        """Radius is max distance from center"""
        # Points roughly 14km apart from center
        center_lat, center_lon = 28.6139, 77.2090
        coords = [
            (28.6139, 77.2090),  # At center
            (28.7041, 77.1025),  # ~14km away
            (28.5237, 77.3152),  # ~14km away in other direction
        ]
        radius = calculate_affected_radius(coords, center_lat, center_lon)
        assert 13 < radius < 16


class TestEventClusteringService:
    """Test the event clustering service"""
    
    @pytest.fixture
    def clustering_service(self):
        """Create clustering service with test parameters"""
        return WeatherEventClusteringService(
            max_distance_km=50.0,
            max_time_window_hours=24.0,
            min_cluster_size=2
        )
    
    @pytest.fixture
    def sample_reports(self):
        """Create sample reports for testing"""
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        return [
            # Cluster 1: Rainfall in Delhi area (3 reports)
            {
                'id': 'r1',
                'event_type': 'rainfall',
                'location': {'lat': 28.6139, 'lon': 77.2090},
                'reported_at': base_time,
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Heavy rain in Delhi'
            },
            {
                'id': 'r2',
                'event_type': 'rainfall',
                'location': {'lat': 28.6500, 'lon': 77.2500},  # ~5km from r1
                'reported_at': base_time + timedelta(hours=2),
                'verification_status': 'verified',
                'confidence_score': 0.90,
                'description': 'Rain continues'
            },
            {
                'id': 'r3',
                'event_type': 'rainfall',
                'location': {'lat': 28.5800, 'lon': 77.1800},  # ~5km from r1
                'reported_at': base_time + timedelta(hours=4),
                'verification_status': 'disputed',
                'confidence_score': 0.60,
                'description': 'Light rain'
            },
            # Cluster 2: Flooding in Mumbai area (2 reports)
            {
                'id': 'r4',
                'event_type': 'flooding',
                'location': {'lat': 19.0760, 'lon': 72.8777},
                'reported_at': base_time + timedelta(hours=1),
                'verification_status': 'verified',
                'confidence_score': 0.95,
                'description': 'Flooding in Mumbai'
            },
            {
                'id': 'r5',
                'event_type': 'flooding',
                'location': {'lat': 19.1000, 'lon': 72.9000},  # ~5km from r4
                'reported_at': base_time + timedelta(hours=3),
                'verification_status': 'verified',
                'confidence_score': 0.92,
                'description': 'Severe flooding'
            },
            # Single report (should not form cluster)
            {
                'id': 'r6',
                'event_type': 'rainfall',
                'location': {'lat': 12.9716, 'lon': 77.5946},  # Bangalore
                'reported_at': base_time,
                'verification_status': 'fake',
                'confidence_score': 0.20,
                'description': 'Fake report'
            }
        ]
    
    def test_empty_reports(self, clustering_service):
        """Test clustering with no reports"""
        clusters = clustering_service.cluster_reports([])
        assert len(clusters) == 0
    
    def test_insufficient_reports(self, clustering_service):
        """Test with fewer reports than min cluster size"""
        reports = [
            {
                'id': 'r1',
                'event_type': 'rainfall',
                'location': {'lat': 28.6139, 'lon': 77.2090},
                'reported_at': datetime.now(),
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain'
            }
        ]
        clusters = clustering_service.cluster_reports(reports)
        assert len(clusters) == 0
    
    def test_basic_clustering(self, clustering_service, sample_reports):
        """Test basic clustering with sample reports"""
        clusters = clustering_service.cluster_reports(sample_reports)
        
        # Should form 2 clusters (Delhi rainfall, Mumbai flooding)
        assert len(clusters) == 2
        
        # Check cluster properties
        for cluster in clusters:
            assert cluster.report_count >= 2
            assert cluster.event_id is not None
            assert cluster.center_lat is not None
            assert cluster.center_lon is not None
            assert cluster.affected_radius_km >= 0
            assert 0.0 <= cluster.avg_confidence_score <= 1.0
    
    def test_event_type_separation(self, clustering_service, sample_reports):
        """Test that different event types are not mixed"""
        clusters = clustering_service.cluster_reports(sample_reports)
        
        # Find rainfall and flooding clusters
        rainfall_cluster = next((c for c in clusters if c.event_type == 'rainfall'), None)
        flooding_cluster = next((c for c in clusters if c.event_type == 'flooding'), None)
        
        assert rainfall_cluster is not None
        assert flooding_cluster is not None
        
        # Rainfall cluster should have 3 reports
        assert rainfall_cluster.report_count == 3
        assert set(rainfall_cluster.report_ids) == {'r1', 'r2', 'r3'}
        
        # Flooding cluster should have 2 reports
        assert flooding_cluster.report_count == 2
        assert set(flooding_cluster.report_ids) == {'r4', 'r5'}
    
    def test_geographic_proximity(self, clustering_service):
        """Test that distant reports are not clustered"""
        base_time = datetime.now()
        reports = [
            {
                'id': 'r1',
                'event_type': 'rainfall',
                'location': {'lat': 28.6139, 'lon': 77.2090},  # Delhi
                'reported_at': base_time,
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain in Delhi'
            },
            {
                'id': 'r2',
                'event_type': 'rainfall',
                'location': {'lat': 12.9716, 'lon': 77.5946},  # Bangalore (~1700km away)
                'reported_at': base_time + timedelta(hours=1),
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain in Bangalore'
            }
        ]
        
        clusters = clustering_service.cluster_reports(reports)
        
        # Should not cluster due to distance
        assert len(clusters) == 0
    
    def test_temporal_proximity(self, clustering_service):
        """Test that temporally distant reports are not clustered"""
        base_time = datetime.now()
        reports = [
            {
                'id': 'r1',
                'event_type': 'rainfall',
                'location': {'lat': 28.6139, 'lon': 77.2090},
                'reported_at': base_time,
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain'
            },
            {
                'id': 'r2',
                'event_type': 'rainfall',
                'location': {'lat': 28.6500, 'lon': 77.2500},  # ~5km away
                'reported_at': base_time + timedelta(hours=30),  # 30 hours later
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain'
            }
        ]
        
        clusters = clustering_service.cluster_reports(reports)
        
        # Should not cluster due to time difference
        assert len(clusters) == 0
    
    def test_verification_summary(self, clustering_service, sample_reports):
        """Test that verification summary is calculated correctly"""
        clusters = clustering_service.cluster_reports(sample_reports)
        
        rainfall_cluster = next((c for c in clusters if c.event_type == 'rainfall'), None)
        assert rainfall_cluster is not None
        
        # Rainfall cluster has 2 verified, 1 disputed
        assert rainfall_cluster.verified_count == 2
        assert rainfall_cluster.disputed_count == 1
        assert rainfall_cluster.fake_count == 0
        assert rainfall_cluster.dominant_status == 'verified'
    
    def test_confidence_calculation(self, clustering_service, sample_reports):
        """Test average confidence score calculation"""
        clusters = clustering_service.cluster_reports(sample_reports)
        
        flooding_cluster = next((c for c in clusters if c.event_type == 'flooding'), None)
        assert flooding_cluster is not None
        
        # Flooding cluster: (0.95 + 0.92) / 2 = 0.935
        expected_confidence = (0.95 + 0.92) / 2
        assert flooding_cluster.avg_confidence_score == pytest.approx(expected_confidence, abs=0.01)
    
    def test_missing_coordinates(self, clustering_service):
        """Test handling of reports without GPS coordinates"""
        base_time = datetime.now()
        reports = [
            {
                'id': 'r1',
                'event_type': 'rainfall',
                'location': None,  # No location
                'reported_at': base_time,
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain'
            },
            {
                'id': 'r2',
                'event_type': 'rainfall',
                'location': {'lat': None, 'lon': None},  # Invalid location
                'reported_at': base_time,
                'verification_status': 'verified',
                'confidence_score': 0.85,
                'description': 'Rain'
            }
        ]
        
        clusters = clustering_service.cluster_reports(reports)
        
        # Should not cluster without valid coordinates
        assert len(clusters) == 0
    
    def test_singleton_service(self):
        """Test get_clustering_service returns configured instance"""
        service = get_clustering_service()
        
        assert isinstance(service, WeatherEventClusteringService)
        assert service.max_distance_km == 50.0
        assert service.max_time_window_hours == 24.0
        assert service.min_cluster_size == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
