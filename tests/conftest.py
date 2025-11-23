import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.core.database import db
from app.main import app


# 1. Database Setup: Connect to DB Pool (Runs for EVERY test function)
# We use scope="function" to ensure the Pool is created on the same Event Loop as the test.
@pytest_asyncio.fixture(scope="function", autouse=True)
async def init_db():
    await db.connect()
    yield
    await db.disconnect()


# 2. Test Isolation: Yield a Connection that ROLLS BACK after use
@pytest_asyncio.fixture(scope="function")
async def db_connection(init_db):
    """
    Yields a database connection.
    Wraps the test in a transaction that is ALWAYS rolled back.
    """
    # Verify pool is ready (it should be, due to init_db autouse=True)
    if not db.pool:
        await db.connect()

    async with db.pool.acquire() as conn:
        # Start a transaction to isolate the test
        tr = conn.transaction()
        await tr.start()
        try:
            yield conn
        finally:
            # Rollback ensures the database is clean for the next test
            await tr.rollback()


# 3. API Client: For E2E tests
@pytest_asyncio.fixture(scope="function")
async def async_client():
    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
    ) as client:
        yield client