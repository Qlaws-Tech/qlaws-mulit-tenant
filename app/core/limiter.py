# app/core/limiter.py

import time
from app.core.cache import cache


class RateLimiter:
    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = int(time.time())
        window_key = f"rate:{key}:{now // window_seconds}"

        count = await cache.get(window_key)
        count = int(count) if count else 0

        if count >= limit:
            return False

        await cache.set(window_key, str(count + 1), ttl=window_seconds)
        return True


limiter = RateLimiter()
