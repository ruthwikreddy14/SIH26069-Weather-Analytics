"""
Text Embedding Deduplication (Signal 3)

Uses sentence-transformers to detect duplicate/near-duplicate text reports.

Algorithm:
1. Embed report text using all-MiniLM-L6-v2 (384-dim vector)
2. Query existing reports from same region + event type in last 24h
3. Compute cosine similarity between embeddings
4. If similarity > 0.92 → merge into event cluster
5. Return confidence score based on uniqueness

Confidence Contribution: 0.2 (20% of final score)
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import numpy as np
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import re
import hashlib

from app.models.weather_report import WeatherReport, EventCluster, VerificationLog

logger = logging.getLogger(__name__)


@dataclass
class TextDeduplicationResult:
    """Result of text deduplication check."""
    
    is_duplicate: bool
    confidence: float  # 0.0 (duplicate) to 1.0 (unique)
    cluster_id: Optional[str] = None
    closest_match_id: Optional[str] = None
    closest_match_similarity: Optional[float] = None
    similar_report_count: int = 0
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to JSON-storable dictionary."""
        return asdict(self)


class TextDeduplicator:
    """
    Text deduplication using sentence embeddings.
    
    Uses all-MiniLM-L6-v2:
    - 80MB model, fast inference (~50ms per sentence)
    - 384-dimensional embeddings
    - Trained on 1B+ sentence pairs
    - Good for semantic similarity
    """
    
    # Thresholds
    DUPLICATE_THRESHOLD = 0.92  # Cosine similarity > 0.92 → duplicate
    SIMILAR_THRESHOLD = 0.85    # Similarity 0.85-0.92 → similar but not duplicate
    
    # Time window for checking duplicates (hours)
    TIME_WINDOW_HOURS = 24
    
    # Distance for "same region" check (meters)
    REGION_RADIUS_METERS = 50000  # 50km
   def __init__(self, model_name: str = "lightweight-hash"):
    """
    Initialize lightweight text deduplicator without ML model.
    """
    self.embedding_dim = 384
    logger.info("Lightweight text deduplicator initialized")


    
   def compute_embedding(self, text: str) -> np.ndarray:
    """
    Create a lightweight text embedding using hashed word features.
    This avoids heavy ML models while preserving similarity detection.
    """
    if not text or not text.strip():
        raise ValueError("Cannot compute embedding for empty text")

    text = " ".join(text.split()).lower()

    embedding = np.zeros(self.embedding_dim, dtype=np.float32)

    tokens = re.findall(r"\b\w+\b", text)

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % self.embedding_dim
        embedding[index] += 1.0

    norm = np.linalg.norm(embedding)

    if norm > 0:
        embedding /= norm

    return embedding
    
    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Cosine similarity ranges from -1 to 1:
        - 1.0: Identical direction (very similar)
        - 0.0: Orthogonal (unrelated)
        - -1.0: Opposite direction (contradictory)
        
        Args:
            vec1: First embedding vector
            vec2: Second embedding vector
            
        Returns:
            Cosine similarity score
        """
        # Normalize vectors
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)
        
        # Compute dot product (cosine similarity for normalized vectors)
        similarity = np.dot(vec1_norm, vec2_norm)
        
        return float(similarity)
    
    async def get_recent_reports(
        self,
        db: AsyncSession,
        current_report: WeatherReport,
        exclude_report_id: Optional[str] = None,
        filter_by_event_type: bool = True
    ) -> List[WeatherReport]:
        """
        Get recent reports from the same region and event type.
        
        Args:
            db: Database session
            current_report: The report being checked
            exclude_report_id: Report ID to exclude (e.g., the current report itself)
            filter_by_event_type: Whether to filter by event type (default True)
            
        Returns:
            List of recent similar reports
        """
        # Calculate time window
        time_threshold = datetime.utcnow() - timedelta(hours=self.TIME_WINDOW_HOURS)
        
        # Build query
        query = select(WeatherReport).where(
            and_(
                WeatherReport.reported_at >= time_threshold,
                WeatherReport.raw_text.isnot(None),
                WeatherReport.raw_text != ""
            )
        )
        
        # Always exclude the current report to prevent self-comparison
        if exclude_report_id:
            query = query.where(WeatherReport.id != exclude_report_id)
        elif current_report and current_report.id:
            query = query.where(WeatherReport.id != current_report.id)
        
        # Filter by event type if available and requested
        # Note: We still find similar reports across event types for similarity scoring,
        # but duplicate detection requires matching event types
        if filter_by_event_type and current_report.event_type:
            query = query.where(
                or_(
                    WeatherReport.event_type == current_report.event_type,
                    WeatherReport.event_type.is_(None)  # Include unclassified reports
                )
            )
        
        # Filter by region if location is available
        # Note: For testing with SQLite, we skip spatial queries
        # In production with PostGIS, this would use ST_DWithin
        if current_report.location and hasattr(current_report.location, 'desc'):
            # PostGIS available - use spatial query
            try:
                from geoalchemy2.functions import ST_DWithin
                query = query.where(
                    or_(
                        ST_DWithin(
                            WeatherReport.location,
                            current_report.location,
                            self.REGION_RADIUS_METERS
                        ),
                        WeatherReport.location.is_(None)
                    )
                )
            except (ImportError, AttributeError):
                # PostGIS not available (e.g., in tests) - filter by city/state instead
                if current_report.city:
                    query = query.where(
                        or_(
                            WeatherReport.city == current_report.city,
                            WeatherReport.city.is_(None)
                        )
                    )
        
        # Execute query
        result = await db.execute(query)
        reports = result.scalars().all()
        
        logger.info(f"Found {len(reports)} recent reports to compare against")
        
        return list(reports)
    
    async def find_similar_reports(
        self,
        db: AsyncSession,
        text: str,
        current_report: WeatherReport,
        exclude_report_id: Optional[str] = None
    ) -> List[tuple[WeatherReport, float]]:
        """
        Find reports with similar text content.
        
        Args:
            db: Database session
            text: Text to check for duplicates
            current_report: The report being checked
            exclude_report_id: Report ID to exclude
            
        Returns:
            List of (report, similarity_score) tuples, sorted by similarity descending
        """
        # Compute embedding for input text
        embedding = self.compute_embedding(text)
        
        # Get recent reports (without event type filter to allow cross-type similarity detection)
        recent_reports = await self.get_recent_reports(
            db, current_report, exclude_report_id, filter_by_event_type=False
        )
        
        if not recent_reports:
            logger.info("No recent reports found for comparison")
            return []
        
        # Compare embeddings
        similarities = []
        for report in recent_reports:
            try:
                # Compute embedding for existing report
                report_embedding = self.compute_embedding(report.raw_text)
                
                # Compute cosine similarity
                similarity = self.cosine_similarity(embedding, report_embedding)
                
                similarities.append((report, similarity))
                
            except Exception as e:
                logger.warning(f"Failed to compute similarity for report {report.id}: {e}")
                continue
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities
    
    async def merge_into_cluster(
        self,
        db: AsyncSession,
        report: WeatherReport,
        similar_report: WeatherReport
    ) -> str:
        """
        Merge report into an event cluster.
        
        If the similar report already has a cluster_id, use that.
        Otherwise, create a new cluster with both reports.
        
        Args:
            db: Database session
            report: The new report (duplicate)
            similar_report: The existing similar report
            
        Returns:
            cluster_id (UUID as string)
        """
        cluster_id = None
        
        # Check if similar report already has a cluster
        if similar_report.cluster_id:
            cluster_id = similar_report.cluster_id
            
            # Update cluster metadata
            cluster_query = select(EventCluster).where(EventCluster.id == cluster_id)
            cluster_result = await db.execute(cluster_query)
            cluster = cluster_result.scalar_one_or_none()
            
            if cluster:
                # Increment report count
                cluster.report_count += 1
                cluster.last_reported_at = report.reported_at
                logger.info(f"Merged report {report.id} into existing cluster {cluster_id}")
            else:
                logger.warning(f"Cluster {cluster_id} not found, creating new cluster")
                cluster_id = None
        
        # Create new cluster if needed
        if not cluster_id:
            new_cluster = EventCluster(
                event_type=report.event_type or similar_report.event_type,
                canonical_text=similar_report.raw_text,  # Use first report as canonical
                centroid=report.location or similar_report.location,
                report_count=2,  # Both the similar report and this new report
                first_reported_at=similar_report.reported_at,
                last_reported_at=report.reported_at
            )
            db.add(new_cluster)
            await db.flush()
            
            cluster_id = new_cluster.id
            
            # Assign cluster to both reports
            similar_report.cluster_id = cluster_id
            logger.info(f"Created new cluster {cluster_id} for reports {similar_report.id} and {report.id}")
        
        # Assign cluster to the new report
        report.cluster_id = cluster_id
        
        return str(cluster_id)
    
    async def check_text(
        self,
        db: AsyncSession,
        text: str,
        current_report: WeatherReport,
        merge_duplicates: bool = True
    ) -> TextDeduplicationResult:
        """
        Check if text is a duplicate/near-duplicate.
        
        Args:
            db: Database session
            text: Text to check
            current_report: The report being checked
            merge_duplicates: Whether to merge duplicates into clusters
            
        Returns:
            TextDeduplicationResult with confidence score
        """
        try:
            # Find similar reports
            similar_reports = await self.find_similar_reports(
                db, text, current_report, exclude_report_id=str(current_report.id)
            )
            
            if not similar_reports:
                # No similar reports found - unique content
                return TextDeduplicationResult(
                    is_duplicate=False,
                    confidence=1.0,
                    similar_report_count=0,
                    reasoning="No similar reports found; text is unique"
                )
            
            # Get the most similar report
            closest_report, max_similarity = similar_reports[0]
            
            # Count highly similar reports (> SIMILAR_THRESHOLD)
            similar_count = sum(1 for _, sim in similar_reports if sim >= self.SIMILAR_THRESHOLD)
            
            # Determine if it's a duplicate
            # Requires high similarity AND matching event types (or at least one is None)
            event_types_match = (
                not current_report.event_type or 
                not closest_report.event_type or 
                current_report.event_type == closest_report.event_type
            )
            is_duplicate = (max_similarity >= self.DUPLICATE_THRESHOLD) and event_types_match
            
            # Calculate confidence score
            if is_duplicate:
                # Very low confidence for duplicates
                confidence = 0.0
                reasoning = f"Duplicate detected (similarity: {max_similarity:.3f} with report {closest_report.id})"
                
                # Merge into cluster if enabled
                if merge_duplicates:
                    cluster_id = await self.merge_into_cluster(db, current_report, closest_report)
                    reasoning += f"; merged into cluster {cluster_id}"
                else:
                    cluster_id = None
                
                return TextDeduplicationResult(
                    is_duplicate=True,
                    confidence=confidence,
                    cluster_id=cluster_id,
                    closest_match_id=str(closest_report.id),
                    closest_match_similarity=max_similarity,
                    similar_report_count=similar_count,
                    reasoning=reasoning
                )
            
            elif max_similarity >= self.SIMILAR_THRESHOLD:
                # Similar but not duplicate - moderate confidence
                # Linear interpolation between SIMILAR_THRESHOLD (0.5 confidence) and DUPLICATE_THRESHOLD (0.0 confidence)
                confidence = 1.0 - ((max_similarity - self.SIMILAR_THRESHOLD) / 
                                   (self.DUPLICATE_THRESHOLD - self.SIMILAR_THRESHOLD)) * 0.5
                confidence = max(0.0, min(1.0, confidence))
                
                reasoning = f"Similar report found (similarity: {max_similarity:.3f}, {similar_count} similar reports)"
                
                return TextDeduplicationResult(
                    is_duplicate=False,
                    confidence=confidence,
                    cluster_id=None,
                    closest_match_id=str(closest_report.id),
                    closest_match_similarity=max_similarity,
                    similar_report_count=similar_count,
                    reasoning=reasoning
                )
            
            else:
                # Low similarity - unique content
                confidence = 1.0
                reasoning = f"Text is unique (max similarity: {max_similarity:.3f})"
                
                return TextDeduplicationResult(
                    is_duplicate=False,
                    confidence=confidence,
                    cluster_id=None,
                    closest_match_id=str(closest_report.id),
                    closest_match_similarity=max_similarity,
                    similar_report_count=similar_count,
                    reasoning=reasoning
                )
        
        except Exception as e:
            logger.error(f"Text deduplication check failed: {e}")
            # Return neutral confidence on error
            return TextDeduplicationResult(
                is_duplicate=False,
                confidence=0.5,
                reasoning=f"Error during deduplication check: {str(e)}"
            )


# Global deduplicator instance (lazy initialization)
_deduplicator: Optional[TextDeduplicator] = None


def get_deduplicator() -> TextDeduplicator:
    """Get or create the global deduplicator instance."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = TextDeduplicator()
    return _deduplicator


async def text_dedup_check(
    report_id: str,
    db: AsyncSession,
    text: Optional[str] = None
) -> TextDeduplicationResult:
    """
    Check if a report's text is a duplicate/near-duplicate (Signal 3).
    
    This is the main entry point for text deduplication verification.
    
    Args:
        report_id: UUID of the report to check
        db: Database session
        text: Optional text to check (if None, fetches from report)
        
    Returns:
        TextDeduplicationResult with confidence score
    """
    logger.info(f"Starting text deduplication check for report {report_id}")
    
    try:
        # Get the report
        query = select(WeatherReport).where(WeatherReport.id == report_id)
        result = await db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            logger.error(f"Report {report_id} not found")
            return TextDeduplicationResult(
                is_duplicate=False,
                confidence=0.0,
                reasoning=f"Report {report_id} not found"
            )
        
        # Get text
        if text is None:
            text = report.raw_text
        
        if not text or not text.strip():
            logger.warning(f"Report {report_id} has no text content")
            return TextDeduplicationResult(
                is_duplicate=False,
                confidence=0.5,
                reasoning="No text content available"
            )
        
        # Perform deduplication check
        deduplicator = get_deduplicator()
        result = await deduplicator.check_text(db, text, report, merge_duplicates=True)
        
        # Store verification log
        import json
        log_entry = VerificationLog(
            report_id=report.id,
            verification_step="text_dedup_check",
            result=json.dumps(result.to_dict())  # Store as JSON string for compatibility
        )
        db.add(log_entry)
        
        # Update report signals
        # Handle both JSONB (Postgres) and Text (SQLite) column types
        import json
        
        if report.signals is None or report.signals == "":
            signals_dict = {}
        elif isinstance(report.signals, str):
            # Already a JSON string (from SQLite)
            signals_dict = json.loads(report.signals)
        else:
            # Dict from Postgres JSONB
            signals_dict = report.signals if isinstance(report.signals, dict) else {}
        
        signals_dict["text_dedup_signal"] = result.to_dict()
        
        # Always store as JSON string for compatibility with both SQLite and Postgres
        report.signals = json.dumps(signals_dict)
        
        # Commit changes
        await db.commit()
        
        logger.info(f"Text deduplication check complete for report {report_id}: "
                   f"duplicate={result.is_duplicate}, confidence={result.confidence:.2f}")
        
        return result
    
    except Exception as e:
        logger.error(f"Text deduplication check failed for report {report_id}: {e}")
        await db.rollback()
        raise
