import asyncio
import logging
import sys
from urllib.parse import urlparse

import asyncpg
import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("connection_check")

MAX_RETRIES = 30
RETRY_INTERVAL = 2  # seconds


async def check_postgres():
    """Attempt to connect to PostgreSQL."""
    dsn = settings.DATABASE_URL
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Checking PostgreSQL connection (Attempt {attempt}/{MAX_RETRIES})...")
            conn = await asyncpg.connect(dsn)
            await conn.close()
            logger.info("✅ PostgreSQL is ready!")
            return True
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL not ready yet: {e}")
            await asyncio.sleep(RETRY_INTERVAL)
    return False


async def check_redis():
    """Attempt to ping Redis with fallback for local development."""
    url = settings.REDIS_URL

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Checking Redis connection (Attempt {attempt}/{MAX_RETRIES})...")
            client = redis.from_url(url, decode_responses=True)
            if await client.ping():
                await client.close()
                logger.info("✅ Redis is ready!")
                return True
        except (RedisConnectionError, OSError) as e:
            logger.warning(f"⚠️ Redis connection failed to {url}: {e}")

            # Fallback: If we are on host trying to reach a docker container name, try localhost
            # This handles the case where .env has 'redis-cache' but we run python locally
            try:
                parsed = urlparse(url)
                if parsed.hostname not in ("localhost", "127.0.0.1"):
                    fallback_url = url.replace(parsed.hostname, "localhost")
                    logger.info(f"🔄 Attempting fallback to localhost: {fallback_url}")

                    fallback_client = redis.from_url(fallback_url, decode_responses=True)
                    if await fallback_client.ping():
                        await fallback_client.close()
                        logger.warning("✅ Redis is ready via LOCALHOST fallback. (Note: Config uses Docker hostname)")
                        return True
            except Exception as fallback_e:
                logger.warning(f"⚠️ Fallback to localhost also failed: {fallback_e}")

            await asyncio.sleep(RETRY_INTERVAL)
        except Exception as e:
            logger.warning(f"⚠️ Unexpected Redis error: {e}")
            await asyncio.sleep(RETRY_INTERVAL)

    return False


async def main():
    """Run checks concurrently."""
    # Run both checks in parallel
    results = await asyncio.gather(check_postgres(), check_redis())

    if all(results):
        logger.info("🚀 All critical services are UP. Starting application...")
        sys.exit(0)
    else:
        logger.error("❌ Critical services failed to start. Aborting.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Connection check cancelled.")
        sys.exit(1)