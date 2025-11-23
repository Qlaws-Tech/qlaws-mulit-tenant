import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.core.security import verify_password


@pytest.mark.asyncio
async def test_login_flow(async_client: AsyncClient, db_connection):
    # 1. Setup Data (Tenant + User)
    tenant_repo = TenantRepository(db_connection)

    # FIX: Added required admin fields to satisfy TenantCreate validation
    tenant = await tenant_repo.create(TenantCreate(
        name="Auth Corp",
        plan="startup",
        admin_email="admin@authcorp.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Auth Admin"  # <-- Added
    ))

    user_repo = UserRepository(db_connection)
    # Set RLS context to create user
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

    user_pw = "securePass123"
    await user_repo.create_user(UserCreate(
        email="admin@authcorp.com",
        password=user_pw,
        display_name="Admin"
    ))

    # ========================================================================
    # THE FIX: Force FastAPI to use the SAME connection as the test
    # This allows the API to see the uncommitted data created above.
    # ========================================================================
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db
    # ========================================================================

    try:
        # 2. Attempt Login via API
        login_payload = {
            "email": "admin@authcorp.com",
            "password": user_pw,
            "tenant_id": str(tenant.tenant_id)
        }

        response = await async_client.post("/api/v1/auth/login", json=login_payload)

        # 3. Assertions
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        print(f"\nLogin Successful! Token: {data['access_token'][:20]}...")

    finally:
        # Clean up: Remove override so it doesn't affect other tests
        app.dependency_overrides.clear()