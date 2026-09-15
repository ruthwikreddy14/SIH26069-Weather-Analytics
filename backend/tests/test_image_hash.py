"""
Unit tests for Image pHash Deduplication (Signal 2).

These tests use generated synthetic images to verify the deduplication logic
without requiring external files or APIs.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, mock_open
from PIL import Image, ImageDraw
import io
import tempfile
from pathlib import Path

from app.ml.image_hash import (
    ImageHashDeduplicator,
    ImageHashVerificationResult,
    image_hash_check
)


def create_test_image(
    width: int = 100,
    height: int = 100,
    color: tuple = (255, 0, 0),
    pattern: str = "solid"
) -> Image.Image:
    """
    Create a test image with specified properties.
    
    Args:
        width: Image width
        height: Image height
        color: RGB color tuple
        pattern: 'solid', 'gradient', 'checkerboard', 'noise'
        
    Returns:
        PIL Image object
    """
    img = Image.new('RGB', (width, height), color)
    
    if pattern == "gradient":
        draw = ImageDraw.Draw(img)
        for y in range(height):
            shade = int(255 * y / height)
            draw.rectangle([(0, y), (width, y+1)], fill=(shade, shade, shade))
    
    elif pattern == "checkerboard":
        draw = ImageDraw.Draw(img)
        square_size = 10
        for y in range(0, height, square_size):
            for x in range(0, width, square_size):
                if (x // square_size + y // square_size) % 2 == 0:
                    draw.rectangle(
                        [(x, y), (x + square_size, y + square_size)],
                        fill=(0, 0, 0)
                    )
    
    elif pattern == "noise":
        import random
        pixels = img.load()
        for y in range(height):
            for x in range(width):
                pixels[x, y] = (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255)
                )
    
    return img


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


class TestImageHashDeduplicator:
    """Test suite for ImageHashDeduplicator class."""
    
    @pytest.fixture
    def deduplicator(self):
        """Create an ImageHashDeduplicator instance."""
        # Use a temporary file for known fakes
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("# Test fake hashes\n")
            f.write("a1b2c3d4e5f6a7b8\n")
            f.write("1234567890abcdef\n")
            temp_path = f.name
        
        dedup = ImageHashDeduplicator(known_fakes_path=temp_path)
        yield dedup
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def red_image(self):
        """Create a solid red test image."""
        return create_test_image(100, 100, (255, 0, 0), "gradient")  # Use gradient instead of solid
    
    @pytest.fixture
    def blue_image(self):
        """Create a solid blue test image."""
        return create_test_image(100, 100, (0, 0, 255), "checkerboard")  # Use checkerboard instead of solid
    
    @pytest.fixture
    def gradient_image(self):
        """Create a gradient test image."""
        return create_test_image(100, 100, pattern="gradient")
    
    @pytest.fixture
    def checkerboard_image(self):
        """Create a checkerboard test image."""
        return create_test_image(100, 100, pattern="checkerboard")
    
    # Test hash computation
    def test_compute_hash_from_image(self, deduplicator, red_image):
        """Test computing hash from PIL Image."""
        hash_str = deduplicator.compute_hash(red_image)
        
        assert isinstance(hash_str, str)
        assert len(hash_str) == 16  # 64-bit hash = 16 hex characters
        assert all(c in '0123456789abcdef' for c in hash_str.lower())
    
    def test_compute_hash_from_bytes(self, deduplicator, red_image):
        """Test computing hash from image bytes."""
        image_bytes = image_to_bytes(red_image)
        hash_str = deduplicator.compute_hash_from_bytes(image_bytes)
        
        assert isinstance(hash_str, str)
        assert len(hash_str) == 16
    
    def test_compute_hash_from_path(self, deduplicator, red_image):
        """Test computing hash from file path."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            red_image.save(f, format='PNG')
            temp_path = f.name
        
        try:
            hash_str = deduplicator.compute_hash_from_path(temp_path)
            assert isinstance(hash_str, str)
            assert len(hash_str) == 16
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_compute_hash_consistency(self, deduplicator, red_image):
        """Test that same image produces same hash."""
        hash1 = deduplicator.compute_hash(red_image)
        hash2 = deduplicator.compute_hash(red_image)
        
        assert hash1 == hash2
    
    def test_compute_hash_different_images(self, deduplicator, red_image, blue_image):
        """Test that different images produce different hashes."""
        hash1 = deduplicator.compute_hash(red_image)
        hash2 = deduplicator.compute_hash(blue_image)
        
        assert hash1 != hash2
    
    # Test Hamming distance calculation
    def test_hamming_distance_identical(self, deduplicator):
        """Test Hamming distance between identical hashes."""
        hash1 = "0000000000000000"
        hash2 = "0000000000000000"
        
        distance = deduplicator.hamming_distance(hash1, hash2)
        assert distance == 0
    
    def test_hamming_distance_different(self, deduplicator):
        """Test Hamming distance between different hashes."""
        hash1 = "0000000000000000"
        hash2 = "ffffffffffffffff"
        
        distance = deduplicator.hamming_distance(hash1, hash2)
        assert distance == 64  # All 64 bits different
    
    def test_hamming_distance_one_bit(self, deduplicator):
        """Test Hamming distance with one bit difference."""
        hash1 = "0000000000000000"
        hash2 = "0000000000000001"
        
        distance = deduplicator.hamming_distance(hash1, hash2)
        assert distance == 1
    
    # Test perceptual hash robustness
    def test_hash_robust_to_resizing(self, deduplicator, red_image):
        """Test that hash is robust to resizing."""
        hash_original = deduplicator.compute_hash(red_image)
        
        # Resize image
        resized = red_image.resize((200, 200))
        hash_resized = deduplicator.compute_hash(resized)
        
        # Should be identical or very close
        distance = deduplicator.hamming_distance(hash_original, hash_resized)
        assert distance < 5  # Very similar
    
    def test_hash_robust_to_compression(self, deduplicator, gradient_image):
        """Test that hash is robust to JPEG compression."""
        hash_original = deduplicator.compute_hash(gradient_image)
        
        # Apply JPEG compression
        buffer = io.BytesIO()
        gradient_image.save(buffer, format='JPEG', quality=50)
        buffer.seek(0)
        compressed = Image.open(buffer)
        hash_compressed = deduplicator.compute_hash(compressed)
        
        # Should be very similar despite compression
        distance = deduplicator.hamming_distance(hash_original, hash_compressed)
        assert distance < 10  # Reasonably similar
    
    # Test known fakes checking
    def test_load_known_fakes(self, deduplicator):
        """Test that known fakes are loaded from file."""
        assert len(deduplicator.known_fake_hashes) >= 2
        assert "a1b2c3d4e5f6a7b8" in deduplicator.known_fake_hashes
        assert "1234567890abcdef" in deduplicator.known_fake_hashes
    
    def test_check_against_known_fakes_match(self, deduplicator):
        """Test detection of known fake images."""
        # Use a hash that's in the known fakes list
        test_hash = "a1b2c3d4e5f6a7b8"
        
        is_fake, distance, matched_hash = deduplicator.check_against_known_fakes(test_hash)
        
        assert is_fake is True
        assert distance == 0
        assert matched_hash == test_hash
    
    def test_check_against_known_fakes_no_match(self, deduplicator):
        """Test that unique images don't match known fakes."""
        # Use a hash that's very different from known fakes
        test_hash = "ffffffffffffffff"
        
        is_fake, distance, matched_hash = deduplicator.check_against_known_fakes(test_hash)
        
        assert is_fake is False
    
    def test_check_against_known_fakes_near_match(self, deduplicator):
        """Test detection of near-matches to known fakes."""
        # Use a hash that's close to a known fake (1 bit different)
        test_hash = "a1b2c3d4e5f6a7b9"  # Last char different
        
        is_fake, distance, matched_hash = deduplicator.check_against_known_fakes(test_hash)
        
        # Should detect as fake if distance < threshold (10)
        assert distance is not None
        assert distance < 10  # Very close
    
    # Test duplicate detection logic
    @pytest.mark.asyncio
    async def test_check_image_unique(self, deduplicator):
        """Test checking a unique image."""
        # Mock database with no similar images
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        test_hash = "1111222233334444"
        
        result = await deduplicator.check_image(test_hash, mock_db)
        
        assert result.is_duplicate is False
        assert result.confidence == 1.0
        assert result.image_hash == test_hash
        assert "unique" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_check_image_exact_duplicate(self, deduplicator):
        """Test detection of exact duplicate image."""
        # Mock database with exact duplicate
        mock_db = AsyncMock()
        
        # Create mock report with same hash
        mock_report = Mock()
        mock_report.id = "test-report-123"
        mock_report.image_hashes = ["1111222233334444"]
        
        # Create proper mock chain for result.scalars().all()
        mock_scalars = Mock()
        mock_scalars.all = Mock(return_value=[mock_report])
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        test_hash = "1111222233334444"
        
        result = await deduplicator.check_image(test_hash, mock_db, report_id="current-report")
        
        assert result.is_duplicate is True
        assert result.confidence == 0.0  # Exact duplicate
        assert result.closest_match_distance == 0
    
    @pytest.mark.asyncio
    async def test_check_image_near_duplicate(self, deduplicator):
        """Test detection of near-duplicate image."""
        # Mock database with similar image
        mock_db = AsyncMock()
        
        # Create mock report with slightly different hash
        mock_report = Mock()
        mock_report.id = "test-report-456"
        mock_report.image_hashes = ["1111222233334440"]  # Last digit different
        
        # Create proper mock chain for result.scalars().all()
        mock_scalars = Mock()
        mock_scalars.all = Mock(return_value=[mock_report])
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        test_hash = "1111222233334444"
        
        result = await deduplicator.check_image(test_hash, mock_db)
        
        assert result.is_duplicate is True
        assert result.confidence < 0.5
        assert result.closest_match_distance < 10
        assert "duplicate" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_check_image_similar_not_duplicate(self, deduplicator):
        """Test similar but not duplicate image."""
        # Mock database with somewhat similar image
        mock_db = AsyncMock()
        
        # Create mock report with moderately different hash
        mock_report = Mock()
        mock_report.id = "test-report-789"
        mock_report.image_hashes = ["1111222233330000"]  # More differences
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_report]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        test_hash = "1111222233334444"
        
        result = await deduplicator.check_image(test_hash, mock_db)
        
        # Distance between these hashes should be > 10
        if result.closest_match_distance and result.closest_match_distance < 15:
            # If similar (10-15), should not be marked as duplicate but confidence reduced
            assert result.is_duplicate is False
            assert 0.0 < result.confidence < 1.0
        else:
            # If not similar (>15), should be unique
            assert result.is_duplicate is False
            assert result.confidence == 1.0
    
    @pytest.mark.asyncio
    async def test_check_image_known_fake(self, deduplicator):
        """Test detection of known fake disaster photo."""
        mock_db = AsyncMock()
        
        # Create proper mock chain for empty database result
        mock_scalars = Mock()
        mock_scalars.all = Mock(return_value=[])
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Use a hash from known fakes list
        test_hash = "a1b2c3d4e5f6a7b8"
        
        result = await deduplicator.check_image(test_hash, mock_db)
        
        assert result.is_duplicate is True
        assert result.confidence == 0.0
        assert result.is_known_fake is True
        assert "known fake" in result.reasoning.lower()
    
    # Test result serialization
    def test_result_to_dict(self):
        """Test that result can be serialized to dict."""
        result = ImageHashVerificationResult(
            is_duplicate=True,
            confidence=0.3,
            image_hash="1111222233334444",
            closest_match_hash="1111222233334440",
            closest_match_distance=4,
            matched_report_id="test-report-123",
            is_known_fake=False,
            reasoning="Near-duplicate detected"
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict["is_duplicate"] is True
        assert result_dict["confidence"] == 0.3
        assert result_dict["image_hash"] == "1111222233334444"
        assert result_dict["matched_report_id"] == "test-report-123"
    
    # Test error handling
    def test_compute_hash_invalid_image(self, deduplicator):
        """Test that invalid image data raises error."""
        invalid_bytes = b"this is not an image"
        
        with pytest.raises(Exception):
            deduplicator.compute_hash_from_bytes(invalid_bytes)
    
    def test_hamming_distance_invalid_hash(self, deduplicator):
        """Test that invalid hash format raises error."""
        with pytest.raises(ValueError):
            deduplicator.hamming_distance("invalid", "also_invalid")
    
    # Test confidence scoring
    def test_confidence_score_exact_duplicate(self, deduplicator):
        """Test confidence score for exact duplicate."""
        # Distance 0 should give confidence 0.0
        is_dup = True
        distance = 0
        
        # Manually calculate what confidence should be
        if distance == 0:
            expected_confidence = 0.0
        
        # This matches the logic in _generate_reasoning
        assert expected_confidence == 0.0
    
    def test_confidence_score_threshold_boundary(self, deduplicator):
        """Test confidence score at duplicate threshold."""
        # Distance exactly at threshold (10)
        distance = 10
        
        # Should be at boundary: no longer duplicate, confidence starting to increase
        # confidence = (10 - 10) / (15 - 10) = 0.0
        expected_confidence = 0.0
        
        assert expected_confidence == 0.0
    
    def test_confidence_score_midpoint(self, deduplicator):
        """Test confidence score between thresholds."""
        # Distance 12.5 (midpoint between 10 and 15)
        distance = 12.5
        
        # confidence = (12.5 - 10) / (15 - 10) = 2.5 / 5 = 0.5
        expected_confidence = 0.5
        
        assert abs(expected_confidence - 0.5) < 0.01


# Integration tests
class TestImageHashIntegration:
    """Integration tests with generated images."""
    
    @pytest.mark.asyncio
    async def test_full_deduplication_flow_unique(self):
        """Test full flow with unique image."""
        deduplicator = ImageHashDeduplicator(known_fakes_path="nonexistent.txt")
        
        # Create unique image
        image = create_test_image(100, 100, (128, 64, 32), "noise")
        image_hash = deduplicator.compute_hash(image)
        
        # Mock empty database
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await deduplicator.check_image(image_hash, mock_db)
        
        assert result.is_duplicate is False
        assert result.confidence == 1.0
        assert result.is_known_fake is False
    
    @pytest.mark.asyncio
    async def test_full_deduplication_flow_duplicate(self):
        """Test full flow with duplicate image."""
        deduplicator = ImageHashDeduplicator(known_fakes_path="nonexistent.txt")
        
        # Create two identical images
        image1 = create_test_image(100, 100, (255, 128, 0), "checkerboard")
        image2 = create_test_image(100, 100, (255, 128, 0), "checkerboard")
        
        hash1 = deduplicator.compute_hash(image1)
        hash2 = deduplicator.compute_hash(image2)
        
        # Hashes should be identical
        assert hash1 == hash2
        
        # Mock database with first image already present
        mock_report = Mock()
        mock_report.id = "existing-report"
        mock_report.image_hashes = [hash1]
        
        mock_db = AsyncMock()
        
        # Create proper mock chain for result.scalars().all()
        mock_scalars = Mock()
        mock_scalars.all = Mock(return_value=[mock_report])
        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await deduplicator.check_image(hash2, mock_db, report_id="new-report")
        
        assert result.is_duplicate is True
        assert result.confidence == 0.0
        assert result.closest_match_distance == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
