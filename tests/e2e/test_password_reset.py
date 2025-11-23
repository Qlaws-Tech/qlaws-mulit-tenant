import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_password_reset_flow(async_client: AsyncClient, db_connection):
    # 1. Override DB
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Setup Data
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="Reset Corp",
            plan="startup",
            admin_email="admin@reset.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Reset Admin"  # <-- Added
        ))

        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        old_pw = "oldpassword123"
        await user_repo.create_user(UserCreate(email="forgot@test.com", password=old_pw, display_name="Forgot User"))

        # 3. Request Reset
        resp_forgot = await async_client.post("/api/v1/auth/forgot-password", json={"email": "forgot@test.com"})
        assert resp_forgot.status_code == 202
        # Capture the debug token (Simulating clicking email link)
        reset_token = resp_forgot.json()["debug_token"]
        assert reset_token is not None

        # 4. Reset Password
        new_pw = "newsecurepassword123"
        resp_reset = await async_client.post("/api/v1/auth/reset-password", json={
            "token": reset_token,
            "new_password": new_pw
        })
        assert resp_reset.status_code == 200

        # 5. Verify Login with NEW password
        resp_login = await async_client.post("/api/v1/auth/login", json={
            "email": "forgot@test.com", "password": new_pw, "tenant_id": str(tenant.tenant_id)
        })
        assert resp_login.status_code == 200

        # 6. Verify Login with OLD password fails
        resp_fail = await async_client.post("/api/v1/auth/login", json={
            "email": "forgot@test.com", "password": old_pw, "tenant_id": str(tenant.tenant_id)
        })
        assert resp_fail.status_code == 401

    finally:
        app.dependency_overrides.clear()