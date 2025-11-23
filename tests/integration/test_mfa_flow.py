import pytest
import pyotp
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_mfa_setup_flow(async_client: AsyncClient, db_connection):
    # 1. Override DB
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Setup Data
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="MFA Corp",
            plan="enterprise",
            admin_email="admin@mfa.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="MFA Admin"  # <-- Added
        ))

        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        # Create User (Password length fixed to satisfy validation if needed)
        await user_repo.create_user(UserCreate(
            email="secure@mfa.com",
            password="securepassword123",
            display_name="User"
        ))

        # 3. Login
        resp = await async_client.post("/api/v1/auth/login", json={
            "email": "secure@mfa.com", "password": "securepassword123", "tenant_id": str(tenant.tenant_id)
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Get MFA Secret
        resp_setup = await async_client.get("/api/v1/auth/mfa/setup", headers=headers)
        assert resp_setup.status_code == 200
        setup_data = resp_setup.json()
        secret = setup_data["secret"]
        assert len(secret) > 0

        # 5. Generate Valid TOTP Code (Simulating User's Phone)
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        # 6. Verify & Enable
        payload = {
            "secret": secret,
            "code": valid_code
        }
        resp_verify = await async_client.post("/api/v1/auth/mfa/verify", json=payload, headers=headers)
        assert resp_verify.status_code == 200
        mfa_data = resp_verify.json()

        assert mfa_data["enabled"] is True
        assert mfa_data["method_type"] == "totp"
        print("\nMFA Successfully Enabled!")

    finally:
        app.dependency_overrides.clear()