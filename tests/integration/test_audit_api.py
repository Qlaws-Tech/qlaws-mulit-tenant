import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate


@pytest.mark.asyncio
async def test_audit_logs_isolation(async_client: AsyncClient, db_connection):
    # 1. Override DB for isolation
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Setup Tenant A
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant_a = await tenant_repo.create(TenantCreate(
            name="Audit Corp A",
            plan="startup",
            admin_email="admin@audit-a.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Audit Admin A"  # <-- Added
        ))

        # Manually seed an Audit Log for Tenant A
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_a.tenant_id))
        audit_repo = AuditRepository(db_connection)
        await audit_repo.log_event(AuditLogCreate(
            action_type="TEST_ACTION_A", resource_type="system", resource_id="1", details={}
        ))

        # 3. Setup Tenant B
        # FIX: Added required admin fields for Tenant B
        tenant_b = await tenant_repo.create(TenantCreate(
            name="Audit Corp B",
            plan="startup",
            admin_email="admin@audit-b.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Audit Admin B"  # <-- Added
        ))

        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b.tenant_id))
        await audit_repo.log_event(AuditLogCreate(
            action_type="TEST_ACTION_B", resource_type="system", resource_id="2", details={}
        ))

        # 4. Login as Tenant A Admin
        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_a.tenant_id))

        # Create User manually (since Repo.create only makes tenant row)
        await user_repo.create_user(UserCreate(email="admin@a.com", password="password123", display_name="Admin A"))

        resp = await async_client.post("/api/v1/auth/login", json={
            "email": "admin@a.com", "password": "password123", "tenant_id": str(tenant_a.tenant_id)
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 5. Fetch Logs (Should see ONLY Tenant A)
        resp_logs = await async_client.get("/api/v1/audit/", headers=headers)
        assert resp_logs.status_code == 200
        logs = resp_logs.json()

        assert len(logs) >= 1
        # Check that we see action A
        assert logs[0]["action_type"] == "TEST_ACTION_A"

        # Verify we DO NOT see Tenant B's action
        actions = [l["action_type"] for l in logs]
        assert "TEST_ACTION_B" not in actions

    finally:
        app.dependency_overrides.clear()