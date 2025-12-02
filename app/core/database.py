# app/core/database.py

import asyncpg
from typing import AsyncGenerator, Optional

from app.core.config import settings


class Database:
    """
    Central asyncpg connection pool wrapper.

    - connect() / disconnect() manage the pool lifecycle.
    - get_connection(tenant_id) yields a connection with RLS tenant context set.
    - ping() is used by /health and startup checks.
    """

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self.pool is not None:
            return

        self.pool = await asyncpg.create_pool(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            database=settings.DATABASE_NAME,
            min_size=2,
            max_size=10,
        )

    async def disconnect(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def ping(self) -> bool:
        """
        Lightweight health check used by /health and startup.

        Returns True if the database responds to a simple query.
        """
        try:
            if self.pool is None:
                await self.connect()
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def get_connection(self, tenant_id: str) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Acquire a connection and set RLS tenant context for the duration
        of the transaction:

            SELECT set_config('app.current_tenant_id', <tenant_id>, true);

        This is used by the dependency layer to ensure tenant isolation.
        """
        if self.pool is None:
            await self.connect()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # IMPORTANT: do not use "SET LOCAL app.current_tenant_id = $1"
                # with a parameter; Postgres can't parameterize that syntax.
                # Use set_config() instead.
                await conn.execute(
                    "SELECT set_config('app.current_tenant_id', $1, true)",
                    tenant_id,
                )
                yield conn


db = Database()
