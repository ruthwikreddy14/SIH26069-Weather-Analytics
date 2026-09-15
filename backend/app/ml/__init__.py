"""
ML verification pipeline for weather reports.
"""

from .verifier import ground_truth_check, GroundTruthVerificationResult
from .image_hash import image_hash_check, ImageHashVerificationResult
from .deduplicator import text_dedup_check, TextDeduplicationResult

__all__ = [
    "ground_truth_check",
    "GroundTruthVerificationResult",
    "image_hash_check",
    "ImageHashVerificationResult",
    "text_dedup_check",
    "TextDeduplicationResult"
]
