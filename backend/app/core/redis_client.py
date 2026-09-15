import redis.asyncio as redis
from typing import Optional

from .config import settings


class RedisClient:
    """Redis client wrapper for async operations."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis."""
        self.redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        # Test connection
        await self.redis.ping()
        print("✓ Redis connected successfully")
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            print("✓ Redis disconnected")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        if not self.redis:
            return None
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, expiration: int = 3600):
        """Set value in Redis with expiration (default: 1 hour)."""
        if not self.redis:
            return False
        return await self.redis.set(key, value, ex=expiration)
    
    async def delete(self, key: str):
        """Delete key from Redis."""
        if not self.redis:
            return False
        return await self.redis.delete(key)


# Global Redis client instance
redis_client = RedisClient()
