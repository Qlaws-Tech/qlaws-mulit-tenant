import asyncpg
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class DatabasePool:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        """Initialize the connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                # FIX: Use uppercase attribute names to match app/core/config.py
                min_size=settings.DATABASE_POOL_MIN_SIZE,
                max_size=settings.DATABASE_POOL_SIZE,
                command_timeout=60
            )
            logger.info("Database pool created successfully.")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise e

    async def disconnect(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed.")

    async def ping(self) -> bool:
        """
        Verifies database connectivity by running a lightweight query.
        """
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

# Global instance
db = DatabasePool()