import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint_success(async_client: AsyncClient):
    """
    Verify that /health returns 200 when services are up.
    (Assuming the test environment DB/Redis are running via conftest)
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"] == "connected"
    assert data["components"]["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_check_db_failure(async_client: AsyncClient):
    """
    Verify that /health returns 503 if DB ping fails.
    """
    # We mock the db.ping method on the global instance
    with patch("app.core.database.db.ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = False

        response = await async_client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["components"]["database"] == "disconnected"


@pytest.mark.asyncio
async def test_health_check_redis_failure(async_client: AsyncClient):
    """
    Verify that /health returns 503 if Redis ping fails.
    """
    with patch("app.core.cache.cache.ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = False

        response = await async_client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["components"]["redis"] == "disconnected"