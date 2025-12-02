# tests/integration/test_sso_encryption.py

import pytest
import json
from httpx import AsyncClient

from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_sso_encryption(async_client: AsyncClient, db_connection):
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 1. Setup tenant & admin user
        tenant_repo = TenantRepository(db_connection)
        tenant = await tenant_repo.create(
            TenantCreate(
                name="SSO Corp",
                plan="enterprise",
                admin_email="admin@sso.com",
                admin_password="password123",
                admin_name="SSO Admin",
            )
        )

        await db_connection.execute(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            str(tenant.tenant_id),
        )

        user_repo = UserRepository(db_connection)
        await user_repo.create_user(
            UserCreate(
                email="admin@sso.com",
                password="password123",
                display_name="Admin",
            )
        )

        # 2. Login to obtain access token
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@sso.com",
                "password": "password123",
                "tenant_id": str(tenant.tenant_id),
            },
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create SSO provider (OIDC)
        payload = {
            "provider_type": "oidc",
            "name": "Corporate Okta",
            "description": "Main IdP",
            "enabled": True,
            "config": {
                "client_id": "okta_123",
                "client_secret": "SUPER_SECRET_VALUE_123",
                "issuer_url": "https://okta.com/tenant",
            },
        }

        resp_create = await async_client.post("/api/v1/sso/", json=payload, headers=headers)
        assert resp_create.status_code == 201, resp_create.text
        data = resp_create.json()

        # API returns decrypted value immediately after create
        assert data["config"]["client_secret"] == "SUPER_SECRET_VALUE_123"

        # 4. Verify DB has ENCRYPTED value
        row = await db_connection.fetchrow(
            "SELECT config FROM sso_providers WHERE name = 'Corporate Okta'"
        )
        db_config = json.loads(row["config"]) if isinstance(row["config"], str) else row["config"]
        # Must be different from plaintext
        assert db_config["client_secret"] != "SUPER_SECRET_VALUE_123"
        # Fernet tokens typically start with 'gAAAA'
        assert isinstance(db_config["client_secret"], str)
        assert "gAAAA" in db_config["client_secret"]

        # 5. Verify list endpoint returns masked secret
        resp_list = await async_client.get("/api/v1/sso/", headers=headers)
        assert resp_list.status_code == 200
        list_data = resp_list.json()
        assert len(list_data) >= 1
        first = list_data[0]
        assert first["config"]["client_secret"] == "********"

    finally:
        app.dependency_overrides.clear()
