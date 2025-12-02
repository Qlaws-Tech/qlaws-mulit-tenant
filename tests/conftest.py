import os
import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import db
from app.core.config import settings
from app.core.cache import cache


@pytest.fixture(scope="session", autouse=True)
async def configure_test_environment():
    """
    Overrides configuration for the test session.
    Forces connections to localhost services.
    """
    # 1. Override Environment Variables
    os.environ["DATABASE_HOST"] = "localhost"
    os.environ["DATABASE_PORT"] = "5432"
    os.environ["DATABASE_USER"] = "qlaws_app"
    os.environ["DATABASE_PASSWORD"] = "app_password"
    os.environ["DATABASE_NAME"] = "qlaws_db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"

    # 2. Override Settings Object
    settings.DATABASE_HOST = "localhost"
    settings.DATABASE_PORT = 5432
    settings.DATABASE_USER = "qlaws_app"
    settings.DATABASE_PASSWORD = "app_password"
    settings.DATABASE_NAME = "qlaws_db"
    settings.REDIS_URL = "redis://localhost:6379/0"

    # 3. Hot-Swap Redis Client
    if cache.redis:
        await cache.redis.close()
    cache.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    yield

    if cache.redis:
        await cache.redis.close()


# 1. Database Setup
@pytest_asyncio.fixture(scope="function", autouse=True)
async def init_db():
    if db.pool:
        await db.disconnect()

    await db.connect()

    # --- CRITICAL FIX: FORCE RLS ---
    # This ensures that even though we are the table owner,
    # RLS policies are strictly applied to prevent data leaks in tests.
    async with db.pool.acquire() as conn:
        await conn.execute("""
            ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
            ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

            ALTER TABLE users ENABLE ROW LEVEL SECURITY;
            ALTER TABLE users FORCE ROW LEVEL SECURITY;

            ALTER TABLE user_tenants ENABLE ROW LEVEL SECURITY;
            ALTER TABLE user_tenants FORCE ROW LEVEL SECURITY;

            ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
            ALTER TABLE roles FORCE ROW LEVEL SECURITY;

            ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
            ALTER TABLE groups FORCE ROW LEVEL SECURITY;
        """)

    yield
    await db.disconnect()


# 2. Test Isolation
@pytest_asyncio.fixture(scope="function")
async def db_connection(init_db):
    if not db.pool:
        await db.connect()

    async with db.pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            yield conn
        finally:
            await tr.rollback()


# 3. API Client
@pytest_asyncio.fixture(scope="function")
async def async_client():
    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
    ) as client:
        yield client