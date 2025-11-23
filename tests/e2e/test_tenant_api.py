import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection


@pytest.mark.asyncio
async def test_create_tenant_endpoint(async_client: AsyncClient, db_connection):
    # 1. Override the API's DB dependency to use our ROLLBACK-enabled connection
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Run the Test
        payload = {
            "name": "New Law Firm",
            "domain": "newlaw.com",
            "plan": "startup",
            "region": "us-west-1",
            # FIX: Added required admin fields for Onboarding
            "admin_email": "admin@newlaw.com",
            "admin_password": "secure_password_123",
            "admin_name": "New Law Admin"
        }

        # The API now writes to the transaction that db_connection will rollback later
        response = await async_client.post("/api/v1/tenants/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Law Firm"
        assert "tenant_id" in data
        assert data["status"] == "active"
        # Verify admin email is returned
        assert data["admin_email"] == "admin@newlaw.com"

    finally:
        # 3. Cleanup Override
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_tenant_invalid_plan(async_client: AsyncClient, db_connection):
    # Apply the override here too (good practice, though validation might not hit DB)
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        payload = {
            "name": "Bad Plan Firm",
            "plan": "mega-unlimited",
            # Even invalid requests need to match schema structure to hit the logic validation
            "admin_email": "admin@bad.com",
            "admin_password": "pass",
            "admin_name": "Bad Admin"
        }
        response = await async_client.post("/api/v1/tenants/", json=payload)
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()