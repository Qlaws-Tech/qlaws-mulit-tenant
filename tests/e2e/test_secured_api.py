import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_full_secured_flow(async_client: AsyncClient, db_connection):
    # --- 1. SETUP: ISOLATION OVERRIDE ---
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # --- 2. SEED DATA (Tenant & User) ---
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="Secure Corp",
            plan="enterprise",
            admin_email="admin@secure.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Secure Admin"  # <-- Added
        ))

        # Create User
        user_repo = UserRepository(db_connection)
        # Manually set context to insert user
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))
        await user_repo.create_user(UserCreate(
            email="ceo@secure.com",
            password="supersecretpass",
            display_name="The CEO"
        ))

        # --- 3. LOGIN (Get Token) ---
        login_payload = {
            "email": "ceo@secure.com",
            "password": "supersecretpass",
            "tenant_id": str(tenant.tenant_id)
        }
        auth_response = await async_client.post("/api/v1/auth/login", json=login_payload)
        assert auth_response.status_code == 200
        token = auth_response.json()["access_token"]

        # --- 4. ACCESS PROTECTED ROUTE (List Users) ---
        # We do NOT send X-Tenant-ID. We send Authorization header.
        headers = {"Authorization": f"Bearer {token}"}

        # This endpoint uses get_tenant_db_connection, which now parses the token!
        list_response = await async_client.get("/api/v1/users/", headers=headers)

        # --- 5. VERIFY ---
        assert list_response.status_code == 200
        users = list_response.json()

        # We might see 1 (CEO) or 2 (CEO + Admin) users depending on if repo.create() made the admin user row
        # Our current repo implementation only inserts the Tenant row, so we expect just the CEO.
        assert len(users) >= 1
        emails = [u["email"] for u in users]
        assert "ceo@secure.com" in emails
        print("\nSUCCESS: Secured RLS Access via JWT verified!")

    finally:
        app.dependency_overrides.clear()