# app/core/cache.py

import redis.asyncio as redis
from typing import Optional

from app.core.config import settings


class Cache:
    """
    Redis cache wrapper.

    - connect() / close() manage the client lifecycle.
    - ping() used by /health and startup checks.
    - get / set / delete for general caching.
    """

    def __init__(self) -> None:
        self.redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        if self.redis is not None:
            return

        self.redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.close()
            self.redis = None

    async def ping(self) -> bool:
        """
        Lightweight health check used by /health and startup.
        """
        try:
            if self.redis is None:
                await self.connect()
            return bool(await self.redis.ping())
        except Exception as ex:
            return False

    async def get(self, key: str):
        if self.redis is None:
            await self.connect()
        return await self.redis.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        if self.redis is None:
            await self.connect()
        await self.redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        if self.redis is None:
            await self.connect()
        await self.redis.delete(key)


cache = Cache()
