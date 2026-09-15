"""
Image pHash Deduplication (Signal 2)

This module implements image deduplication using perceptual hashing (pHash)
to detect recycled disaster photos being reused as "breaking news."

Key Features:
- Computes perceptual hash (pHash) of images using imagehash library
- Compares against existing report image hashes using Hamming distance
- Checks against known fake disaster photo database
- Returns confidence score based on similarity to existing images
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging
from io import BytesIO

from PIL import Image
import imagehash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.weather_report import WeatherReport, VerificationLog

logger = logging.getLogger(__name__)


@dataclass
class ImageHashVerificationResult:
    """Result of image hash deduplication check."""
    
    is_duplicate: bool
    confidence: float  # 0.0 - 1.0 (1.0 = unique, 0.0 = exact duplicate)
    image_hash: Optional[str] = None
    closest_match_hash: Optional[str] = None
    closest_match_distance: Optional[int] = None
    matched_report_id: Optional[str] = None
    is_known_fake: bool = False
    error: Optional[str] = None
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "is_duplicate": self.is_duplicate,
            "confidence": self.confidence,
            "image_hash": self.image_hash,
            "closest_match_hash": self.closest_match_hash,
            "closest_match_distance": self.closest_match_distance,
            "matched_report_id": self.matched_report_id,
            "is_known_fake": self.is_known_fake,
            "error": self.error,
            "reasoning": self.reasoning
        }


class ImageHashDeduplicator:
    """
    Detects duplicate/recycled images using perceptual hashing.
    
    Uses pHash (perceptual hash) which is robust to minor image modifications:
    - Resizing
    - Compression artifacts
    - Color adjustments
    - Minor cropping
    
    Hamming distance < 10 indicates high similarity (likely duplicate).
    """
    
    # Thresholds (from requirements.md)
    DUPLICATE_THRESHOLD = 10  # Hamming distance < 10 = duplicate
    SIMILAR_THRESHOLD = 15    # 10-15 = similar but not exact
    
    def __init__(self, known_fakes_path: Optional[str] = None):
        """
        Initialize image hash deduplicator.
        
        Args:
            known_fakes_path: Path to file containing known fake image hashes
                             (one hash per line). Defaults to data/known_fake_hashes.txt
        """
        if known_fakes_path:
            self.known_fakes_path = known_fakes_path
        else:
            # Try multiple possible locations
            import os
            possible_paths = [
                "data/known_fake_hashes.txt",
                "../data/known_fake_hashes.txt",
                "../../data/known_fake_hashes.txt"
            ]
            self.known_fakes_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    self.known_fakes_path = path
                    break
            if not self.known_fakes_path:
                self.known_fakes_path = "data/known_fake_hashes.txt"  # Fallback
        
        self.known_fake_hashes: List[str] = []
        self._load_known_fakes()
    
    def _load_known_fakes(self):
        """Load known fake image hashes from file."""
        try:
            path = Path(self.known_fakes_path)
            if path.exists():
                with open(path, 'r') as f:
                    self.known_fake_hashes = [
                        line.strip() for line in f 
                        if line.strip() and not line.startswith('#')
                    ]
                logger.info(f"Loaded {len(self.known_fake_hashes)} known fake image hashes")
            else:
                logger.warning(f"Known fakes file not found: {self.known_fakes_path}")
        except Exception as e:
            logger.error(f"Failed to load known fakes: {e}")
    
    def compute_hash(self, image: Image.Image) -> str:
        """
        Compute perceptual hash of an image.
        
        Args:
            image: PIL Image object
            
        Returns:
            Hexadecimal string representation of pHash
        """
        try:
            # Compute perceptual hash (8x8 = 64-bit hash)
            phash = imagehash.phash(image, hash_size=8)
            return str(phash)
        except Exception as e:
            logger.error(f"Failed to compute image hash: {e}")
            raise
    
    def compute_hash_from_bytes(self, image_bytes: bytes) -> str:
        """
        Compute perceptual hash from image bytes.
        
        Args:
            image_bytes: Raw image data
            
        Returns:
            Hexadecimal string representation of pHash
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            return self.compute_hash(image)
        except Exception as e:
            logger.error(f"Failed to load image from bytes: {e}")
            raise
    
    def compute_hash_from_path(self, image_path: str) -> str:
        """
        Compute perceptual hash from image file path.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Hexadecimal string representation of pHash
        """
        try:
            image = Image.open(image_path)
            return self.compute_hash(image)
        except Exception as e:
            logger.error(f"Failed to load image from path {image_path}: {e}")
            raise
    
    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        Calculate Hamming distance between two hashes.
        
        Hamming distance is the number of differing bits between two hashes.
        Lower distance = more similar images.
        
        Args:
            hash1: First hash (hex string)
            hash2: Second hash (hex string)
            
        Returns:
            Hamming distance (0-64 for 8x8 hash)
        """
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2  # imagehash overloads - operator for Hamming distance
        except Exception as e:
            logger.error(f"Failed to compute Hamming distance: {e}")
            # Fallback: manual bit difference calculation
            try:
                int1 = int(hash1, 16)
                int2 = int(hash2, 16)
                xor = int1 ^ int2
                return bin(xor).count('1')
            except:
                raise ValueError(f"Invalid hash format: {hash1}, {hash2}")
    
    def check_against_known_fakes(self, image_hash: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Check if image hash matches known fake disaster photos.
        
        Args:
            image_hash: Hash to check
            
        Returns:
            Tuple of (is_fake, closest_distance, closest_hash)
        """
        if not self.known_fake_hashes:
            return False, None, None
        
        min_distance = float('inf')
        closest_fake_hash = None
        
        for fake_hash in self.known_fake_hashes:
            try:
                distance = self.hamming_distance(image_hash, fake_hash)
                if distance < min_distance:
                    min_distance = distance
                    closest_fake_hash = fake_hash
                    
                # Early exit if exact or near-exact match
                if distance < self.DUPLICATE_THRESHOLD:
                    return True, distance, fake_hash
            except Exception as e:
                logger.warning(f"Failed to compare with fake hash {fake_hash}: {e}")
                continue
        
        # Check if closest match is below threshold
        if min_distance < self.DUPLICATE_THRESHOLD:
            return True, int(min_distance), closest_fake_hash
        
        return False, int(min_distance) if min_distance != float('inf') else None, closest_fake_hash
    
    async def find_similar_images(
        self,
        image_hash: str,
        db: AsyncSession,
        exclude_report_id: Optional[str] = None
    ) -> List[Tuple[str, int, str]]:
        """
        Find similar images in the database.
        
        Args:
            image_hash: Hash to compare
            db: Database session
            exclude_report_id: Report ID to exclude from search (current report)
            
        Returns:
            List of tuples: (report_id, hamming_distance, matched_hash)
            Sorted by distance (most similar first)
        """
        try:
            # Fetch all reports with images
            query = select(WeatherReport).where(
                WeatherReport.image_hashes.isnot(None)
            )
            
            if exclude_report_id:
                query = query.where(WeatherReport.id != exclude_report_id)
            
            result = await db.execute(query)
            reports = result.scalars().all()
            
            # Compare against all existing image hashes
            similarities = []
            for report in reports:
                if not report.image_hashes:
                    continue
                
                for existing_hash in report.image_hashes:
                    try:
                        distance = self.hamming_distance(image_hash, existing_hash)
                        if distance < self.SIMILAR_THRESHOLD:  # Only consider similar images
                            similarities.append((str(report.id), distance, existing_hash))
                    except Exception as e:
                        logger.warning(f"Failed to compare with hash {existing_hash}: {e}")
                        continue
            
            # Sort by distance (most similar first)
            similarities.sort(key=lambda x: x[1])
            return similarities
            
        except Exception as e:
            logger.error(f"Failed to find similar images: {e}")
            return []
    
    async def check_image(
        self,
        image_hash: str,
        db: AsyncSession,
        report_id: Optional[str] = None
    ) -> ImageHashVerificationResult:
        """
        Check an image hash for duplicates.
        
        Args:
            image_hash: Perceptual hash of the image
            db: Database session
            report_id: ID of current report (to exclude from comparison)
            
        Returns:
            ImageHashVerificationResult with confidence score
        """
        # Check against known fake disaster photos first
        is_known_fake, fake_distance, fake_hash = self.check_against_known_fakes(image_hash)
        
        if is_known_fake:
            return ImageHashVerificationResult(
                is_duplicate=True,
                confidence=0.0,  # Zero confidence for known fakes
                image_hash=image_hash,
                closest_match_hash=fake_hash,
                closest_match_distance=fake_distance,
                is_known_fake=True,
                reasoning=f"Image matches known fake disaster photo (distance: {fake_distance})"
            )
        
        # Check against existing report images
        similar_images = await self.find_similar_images(image_hash, db, report_id)
        
        if not similar_images:
            # Unique image
            return ImageHashVerificationResult(
                is_duplicate=False,
                confidence=1.0,
                image_hash=image_hash,
                reasoning="Image is unique; no similar images found"
            )
        
        # Get closest match
        closest_report_id, closest_distance, closest_hash = similar_images[0]
        
        # Determine if duplicate based on threshold
        is_duplicate = bool(closest_distance < self.DUPLICATE_THRESHOLD)
        
        # Calculate confidence (inverse of similarity)
        # Distance 0 = confidence 0.0 (exact duplicate)
        # Distance >= SIMILAR_THRESHOLD = confidence 1.0 (unique)
        if closest_distance == 0:
            confidence = 0.0
        elif closest_distance >= self.SIMILAR_THRESHOLD:
            confidence = 1.0
        else:
            # Linear scale between DUPLICATE_THRESHOLD and SIMILAR_THRESHOLD
            confidence = float((closest_distance - self.DUPLICATE_THRESHOLD) / \
                        (self.SIMILAR_THRESHOLD - self.DUPLICATE_THRESHOLD))
            confidence = max(0.0, min(1.0, confidence))
        
        reasoning = self._generate_reasoning(
            is_duplicate,
            closest_distance,
            len(similar_images)
        )
        
        return ImageHashVerificationResult(
            is_duplicate=is_duplicate,
            confidence=confidence,
            image_hash=image_hash,
            closest_match_hash=closest_hash,
            closest_match_distance=int(closest_distance),
            matched_report_id=closest_report_id,
            is_known_fake=False,
            reasoning=reasoning
        )
    
    def _generate_reasoning(
        self,
        is_duplicate: bool,
        distance: int,
        num_similar: int
    ) -> str:
        """Generate human-readable reasoning for the result."""
        if is_duplicate:
            if distance == 0:
                return f"Exact duplicate image found (Hamming distance: 0)"
            else:
                return f"Near-duplicate image found (Hamming distance: {distance}, threshold: {self.DUPLICATE_THRESHOLD})"
        else:
            if num_similar > 0:
                return f"Similar image found but not duplicate (distance: {distance}, {num_similar} similar images)"
            else:
                return "Image is unique; no similar images in database"


# Async wrapper function for use in the application
async def image_hash_check(
    report_id: str,
    db: AsyncSession,
    image_data: Optional[bytes] = None
) -> ImageHashVerificationResult:
    """
    Perform image hash deduplication for a weather report.
    
    Args:
        report_id: UUID of the weather report
        db: Database session
        image_data: Optional image bytes (if not already stored)
        
    Returns:
        ImageHashVerificationResult with confidence score
    """
    # Fetch report from database
    result = await db.execute(
        select(WeatherReport).where(WeatherReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        logger.error(f"Report {report_id} not found")
        return ImageHashVerificationResult(
            is_duplicate=False,
            confidence=0.5,
            error="Report not found",
            reasoning="Cannot verify non-existent report"
        )
    
    # Check if report has images
    if not report.media_urls and not image_data:
        logger.info(f"Report {report_id} has no images")
        return ImageHashVerificationResult(
            is_duplicate=False,
            confidence=1.0,  # No image = cannot be duplicate
            reasoning="No image to verify; default to unique"
        )
    
    # If report already has image hashes stored, use the first one
    # (In production, would check all images; for MVP, check first one)
    deduplicator = ImageHashDeduplicator()
    
    if report.image_hashes and len(report.image_hashes) > 0:
        # Use existing hash
        image_hash = report.image_hashes[0]
        logger.info(f"Using existing hash for report {report_id}: {image_hash}")
    elif image_data:
        # Compute hash from provided image data
        try:
            image_hash = deduplicator.compute_hash_from_bytes(image_data)
            
            # Store hash in report
            if report.image_hashes:
                report.image_hashes.append(image_hash)
            else:
                report.image_hashes = [image_hash]
            
            logger.info(f"Computed new hash for report {report_id}: {image_hash}")
        except Exception as e:
            logger.error(f"Failed to compute image hash: {e}")
            return ImageHashVerificationResult(
                is_duplicate=False,
                confidence=0.5,
                error=f"Failed to process image: {str(e)}",
                reasoning="Image processing error; cannot verify"
            )
    else:
        # No hash and no image data provided
        return ImageHashVerificationResult(
            is_duplicate=False,
            confidence=1.0,
            reasoning="No image hash available; default to unique"
        )
    
    # Perform deduplication check
    verification_result = await deduplicator.check_image(
        image_hash=image_hash,
        db=db,
        report_id=str(report.id)
    )
    
    # Log verification step
    log_entry = VerificationLog(
        report_id=report.id,
        verification_step="image_hash_check",
        result=verification_result.to_dict()
    )
    db.add(log_entry)
    
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log verification: {e}")
        await db.rollback()
    
    return verification_result
