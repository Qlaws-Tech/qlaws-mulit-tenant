import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_api_key_lifecycle(async_client: AsyncClient, db_connection):
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 1. Setup
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="Key Corp",
            plan="enterprise",
            admin_email="admin@keycorp.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Key Admin"  # <-- Added
        ))

        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        # Create the user that will own the key
        await user_repo.create_user(UserCreate(
            email="dev@keys.com",
            password="password123",
            display_name="Dev"
        ))

        # 2. Login
        resp_login = await async_client.post("/api/v1/auth/login", json={
            "email": "dev@keys.com", "password": "password123", "tenant_id": str(tenant.tenant_id)
        })
        headers = {"Authorization": f"Bearer {resp_login.json()['access_token']}"}

        # 3. Create API Key
        payload = {"name": "Zapier Integration", "scopes": ["user.read"]}
        resp_create = await async_client.post("/api/v1/api-keys/", json=payload, headers=headers)
        assert resp_create.status_code == 201
        data = resp_create.json()

        plain_key = data["plain_key"]
        assert plain_key.startswith("pk_live_")
        assert "key_hash" not in data  # Should never return hash

        # 4. Verify DB Storage (Hashed)
        row = await db_connection.fetchrow("SELECT key_hash FROM api_keys WHERE name = 'Zapier Integration'")
        assert row['key_hash'] != plain_key

        # 5. List Keys
        resp_list = await async_client.get("/api/v1/api-keys/", headers=headers)
        assert len(resp_list.json()) == 1
        assert "plain_key" not in resp_list.json()[0]

        # 6. Revoke
        key_id = data["api_key_id"]
        await async_client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)

        # 7. Verify Revoked
        resp_list_after = await async_client.get("/api/v1/api-keys/", headers=headers)
        assert len(resp_list_after.json()) == 0

    finally:
        app.dependency_overrides.clear()