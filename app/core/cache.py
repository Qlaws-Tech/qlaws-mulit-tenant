import redis.asyncio as redis
from config_dev import settings
import json
import logging

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        # Initialize client (lazy connection usually)
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def get(self, key: str):
        val = await self.redis.get(key)
        return json.loads(val) if val else None

    async def set(self, key: str, value: dict, expire: int = 60):
        await self.redis.set(key, json.dumps(value), ex=expire)

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def ping(self) -> bool:
        """
        Verifies Redis connectivity.
        Used by the main application health check on startup.
        """
        try:
            return await self.redis.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

cache = CacheService()