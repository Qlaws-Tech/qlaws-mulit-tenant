from typing import AsyncGenerator
from asyncpg import Connection
from fastapi import HTTPException, status
from app.core.database import db


async def get_db_connection() -> AsyncGenerator[Connection, None]:
    """
    Yields a raw database connection from the pool.

    WARNING: This connection does NOT have RLS policies applied yet.
    Use this dependency for:
    1. Tenant Onboarding (creation)
    2. Authentication (login/lookup)
    3. System-level background tasks
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized"
        )

    async with db.pool.acquire() as connection:
        # Start a transaction for every request to ensure atomicity
        async with connection.transaction():
            try:
                yield connection
            except Exception as e:
                # The transaction context manager handles rollback on error,
                # but we log it here for visibility.
                print(f"Database error: {e}")
                raise e