import pytest
from uuid import uuid4
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_cleanup_job(async_client: AsyncClient, db_connection):
    # Override the dependency to use the test's rollback connection
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 1. Setup Tenant
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added missing admin fields required by the updated TenantCreate schema
        tenant = await tenant_repo.create(TenantCreate(
            name="Cleanup Corp",
            plan="startup",
            admin_email="admin@cleanup.com",  # <-- Required field
            admin_password="securepassword123",  # <-- Required field
            admin_name="Cleanup Admin"  # <-- Required field
        ))

        # 2. Setup User (CRITICAL: Needed for Session creation)
        user_repo = UserRepository(db_connection)

        # Set RLS context so we can insert the user
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

        user = await user_repo.create_user(UserCreate(
            email="cleanup@test.com",
            password="password123",
            display_name="Cleanup User"
        ))

        # 3. Seed Expired Data
        # A. Insert Session (Required parent for refresh token)
        session_id = uuid4()
        await db_connection.execute(
            """
            INSERT INTO sessions (
                session_id, user_tenant_id, tenant_id, 
                created_at, last_seen_at, ip_address, device_info
            )
            VALUES (
                $1::uuid, 
                (SELECT user_tenant_id FROM user_tenants WHERE user_id = $2::uuid), 
                $3::uuid, 
                now() - interval '1 year', 
                now() - interval '1 year',
                '127.0.0.1'::inet,
                '{}'::jsonb
            )
            """,
            str(session_id),
            str(user.user_id),
            str(tenant.tenant_id)
        )

        # B. Insert Expired Refresh Token (This is what the cleanup job actually targets)
        await db_connection.execute(
            """
            INSERT INTO refresh_tokens (session_id, token_hash, expires_at)
            VALUES ($1::uuid, 'dummy_expired_hash', now() - interval '1 day')
            """,
            str(session_id)
        )

        # 4. Run Cleanup via API
        headers = {"X-System-Key": "sys_admin_secret_123"}

        resp = await async_client.post("/api/v1/system/cleanup", headers=headers)

        # 5. Verify Results
        assert resp.status_code == 200
        data = resp.json()

        assert data["expired_tokens_deleted"] >= 1
        assert data["message"] == "Cleanup completed successfully"

    finally:
        app.dependency_overrides.clear()