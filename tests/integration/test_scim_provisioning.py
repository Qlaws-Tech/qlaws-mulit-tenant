import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.api_keys.service import ApiKeyService
from app.modules.api_keys.repository import ApiKeyRepository
from app.modules.api_keys.schemas import ApiKeyCreate


@pytest.mark.asyncio
async def test_scim_user_creation(async_client: AsyncClient, db_connection):
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 1. Setup Tenant
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added missing admin fields required by TenantCreate schema
        tenant = await tenant_repo.create(TenantCreate(
            name="SCIM Corp",
            plan="enterprise",
            admin_email="admin@scim.com",  # <-- Added
            admin_password="securepassword123",  # <-- Added
            admin_name="SCIM Admin"  # <-- Added
        ))

        # Set context to create API Key
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        # 2. Generate API Key (The "Okta" token)
        apikey_service = ApiKeyService(ApiKeyRepository(db_connection))
        key_resp = await apikey_service.create_api_key(ApiKeyCreate(name="Okta SCIM", scopes=["scim.write"]))
        scim_token = key_resp.plain_key

        # 3. Call SCIM Endpoint (As Okta)
        # SCIM Payload structure
        scim_payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "employee@scim.com",
            "name": {
                "givenName": "John",
                "familyName": "Doe"
            },
            "emails": [{"value": "employee@scim.com", "primary": True}],
            "active": True
        }

        headers = {
            "Authorization": f"Bearer {scim_token}",
            "Content-Type": "application/scim+json"
        }

        resp = await async_client.post("/scim/v2/Users", json=scim_payload, headers=headers)

        # 4. Verify Response
        assert resp.status_code == 201
        data = resp.json()
        assert data["userName"] == "employee@scim.com"
        user_id = data["id"]

        # 5. Verify DB State
        # Check if user exists and is linked to tenant
        row = await db_connection.fetchrow(
            "SELECT status FROM user_tenants WHERE user_id = $1::uuid AND tenant_id = $2::uuid",
            user_id, str(tenant.tenant_id)
        )
        assert row is not None
        assert row["status"] == "active"
        print("\nSCIM User Provisioning Successful!")

    finally:
        app.dependency_overrides.clear()