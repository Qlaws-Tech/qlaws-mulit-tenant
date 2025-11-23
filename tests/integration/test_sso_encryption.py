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
    # 1. Override DB
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Setup Tenant & Admin
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="SSO Corp",
            plan="enterprise",
            admin_email="admin@sso.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="SSO Admin"  # <-- Added
        ))

        # Set RLS Context
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        # Create the actual user in DB (since Repo.create only makes the tenant row)
        user_repo = UserRepository(db_connection)
        await user_repo.create_user(UserCreate(
            email="admin@sso.com",
            password="password123",
            display_name="Admin"
        ))

        # 3. Login
        resp = await async_client.post("/api/v1/auth/login", json={
            "email": "admin@sso.com", "password": "password123", "tenant_id": str(tenant.tenant_id)
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Create SSO Config
        payload = {
            "provider_type": "oidc",
            "name": "Corporate Okta",
            "config": {
                "client_id": "okta_123",
                "client_secret": "SUPER_SECRET_VALUE_123",
                "issuer_url": "https://okta.com/tenant"
            }
        }

        resp_create = await async_client.post("/api/v1/sso/", json=payload, headers=headers)
        assert resp_create.status_code == 201
        data = resp_create.json()

        # API should return decrypted value immediately after create
        assert data["config"]["client_secret"] == "SUPER_SECRET_VALUE_123"

        # 5. CRITICAL: Verify DB has ENCRYPTED value
        row = await db_connection.fetchrow("SELECT config FROM sso_providers WHERE name = 'Corporate Okta'")
        db_config = json.loads(row['config'])

        assert db_config["client_secret"] != "SUPER_SECRET_VALUE_123"
        assert "gAAAA" in db_config["client_secret"]  # Fernet tokens usually start with gAAAA
        print("\nSUCCESS: Database contains encrypted secret!")

        # 6. Verify List Endpoint returns Masked
        resp_list = await async_client.get("/api/v1/sso/", headers=headers)
        list_data = resp_list.json()
        assert list_data[0]["config"]["client_secret"] == "********"

    finally:
        app.dependency_overrides.clear()