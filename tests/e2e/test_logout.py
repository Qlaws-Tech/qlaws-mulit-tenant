import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_logout_flow(async_client: AsyncClient, db_connection):
    # 1. Override DB for Transaction Isolation
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Setup Data
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="Logout Corp",
            plan="startup",
            admin_email="admin@logout.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Logout Admin"  # <-- Added
        ))

        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        # Create the user we will test logging out with
        await user_repo.create_user(UserCreate(
            email="logout@test.com",
            password="password123",
            display_name="User"
        ))

        # 3. Login
        resp = await async_client.post("/api/v1/auth/login", json={
            "email": "logout@test.com", "password": "password123", "tenant_id": str(tenant.tenant_id)
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Verify Access (Should work)
        resp_before = await async_client.get("/api/v1/users/", headers=headers)
        assert resp_before.status_code == 200

        # 5. LOGOUT
        await async_client.post("/api/v1/auth/logout", headers=headers)

        # 6. Verify Access Denied (Should fail)
        resp_after = await async_client.get("/api/v1/users/", headers=headers)
        assert resp_after.status_code == 401
        assert "revoked" in resp_after.json()["detail"]

    finally:
        app.dependency_overrides.clear()