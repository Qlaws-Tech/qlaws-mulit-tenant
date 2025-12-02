# tests/e2e/test_tenant_api.py

import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection


@pytest.mark.asyncio
async def test_create_tenant_endpoint(async_client: AsyncClient, db_connection):
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        payload = {
            "name": "New Law Firm",
            "domain": "newlaw.com",
            "plan": "startup",
            "region": "us-west-1",
            "admin_email": "admin@newlaw.com",
            "admin_password": "secure_password_123",
            "admin_name": "New Law Admin"
        }

        response = await async_client.post("/api/v1/tenants/", json=payload)

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "New Law Firm"
        assert "tenant_id" in data
        assert data["status"] == "active"
        assert data["admin_email"] == "admin@newlaw.com"

    finally:
        app.dependency_overrides.clear()
