import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate


@pytest.mark.asyncio
async def test_user_context_and_redirect(async_client: AsyncClient, db_connection):
    # 1. Override DB
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 2. Setup Tenant
        tenant_repo = TenantRepository(db_connection)

        # FIX: Provide required admin fields to satisfy TenantCreate schema validation
        # (Even if we don't use them in this specific repo call, Pydantic requires them)
        tenant = await tenant_repo.create(TenantCreate(
            name="Context Corp",
            plan="enterprise",
            admin_email="admin@context.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Context Admin"  # <-- Added
        ))

        # 3. Setup User
        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))
        user = await user_repo.create_user(
            UserCreate(email="ctx@test.com", password="password123", display_name="Context User"))

        # 4. Create Role with 'tenant.manage' Permission
        role_repo = RoleRepository(db_connection)
        # Seed permission
        await db_connection.execute("INSERT INTO permissions (key) VALUES ('tenant.manage') ON CONFLICT DO NOTHING")

        admin_role = await role_repo.create_role(RoleCreate(
            name="Admin",
            permission_keys=["tenant.manage"]
        ))

        # 5. Assign Role to User
        ut_id_row = await db_connection.fetchrow("SELECT user_tenant_id FROM user_tenants WHERE user_id = $1::uuid",
                                                 str(user.user_id))
        await db_connection.execute(
            "INSERT INTO user_roles (user_tenant_id, role_id) VALUES ($1, $2)",
            ut_id_row['user_tenant_id'], admin_role.role_id
        )

        # 6. Login
        resp_login = await async_client.post("/api/v1/auth/login", json={
            "email": "ctx@test.com", "password": "password123", "tenant_id": str(tenant.tenant_id)
        })
        token = resp_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 7. Call /me Endpoint
        resp_me = await async_client.get("/api/v1/users/me", headers=headers)
        assert resp_me.status_code == 200
        data = resp_me.json()

        # 8. Verify Response
        assert data["email"] == "ctx@test.com"
        assert data["tenant_name"] == "Context Corp"
        assert "Admin" in data["roles"]
        assert "tenant.manage" in data["permissions"]

        # 9. Verify Redirect Logic
        assert data["redirect_url"] == "/admin/overview"
        print(f"\nSuccess! User directed to: {data['redirect_url']}")

    finally:
        app.dependency_overrides.clear()