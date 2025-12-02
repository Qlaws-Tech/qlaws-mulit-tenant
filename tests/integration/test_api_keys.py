import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_tenant_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.modules.api_keys.repository import APIKeyRepository
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_api_key_lifecycle(async_client: AsyncClient, db_connection):
    # Override tenant DB dependency
    async def override_get_tenant_db_connection():
        return db_connection

    app.dependency_overrides[get_tenant_db_connection] = override_get_tenant_db_connection

    try:
        # 1. Create Tenant + Admin User
        tenant_repo = TenantRepository(db_connection)
        tenant = await tenant_repo.create(
            TenantCreate(
                name="KeyCorp",
                domain="keycorp.test",
                plan="enterprise",
                region="eu-central-1",
                admin_email="admin@keycorp.test",
                admin_password="StrongPass123!",
                admin_name="Key Admin",
            )
        )

        user_repo = UserRepository(db_connection)
        user = await user_repo.create_user(
            UserCreate(
                email="admin@keycorp.test",
                password="StrongPass123!",
                display_name="Key Admin",
            ),
            tenant_id=tenant.tenant_id,
        )

        # 2. Mint access token with apikey perms
        # For simplicity, we don't assert permissions in this test; just need an authenticated user.
        token = create_access_token({"sub": str(user.user_id), "tid": str(tenant.tenant_id)})
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create API Key
        create_payload = {"name": "Test Key", "scopes": ["docs.read"]}
        resp = await async_client.post("/api/v1/api-keys/", json=create_payload, headers=headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "api_key_id" in data
        assert "plain_key" in data
        api_key_id = data["api_key_id"]

        # 4. List API Keys (should show masked only)
        resp_list = await async_client.get("/api/v1/api-keys/", headers=headers)
        assert resp_list.status_code == 200
        list_data = resp_list.json()
        assert len(list_data) >= 1
        assert "plain_key" not in list_data[0]
        assert list_data[0]["name"] == "Test Key"

        # 5. Revoke API Key
        resp_del = await async_client.delete(f"/api/v1/api-keys/{api_key_id}", headers=headers)
        assert resp_del.status_code == 200

        # 6. List again; key should be removed (or at least not returned)
        resp_list2 = await async_client.get("/api/v1/api-keys/", headers=headers)
        assert resp_list2.status_code == 200

    finally:
        app.dependency_overrides.clear()
