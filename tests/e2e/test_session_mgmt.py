import pytest
from httpx import AsyncClient
from app.main import app
from app.dependencies.database import get_db_connection
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_session_refresh_flow(async_client: AsyncClient, db_connection):
    async def override_get_db():
        yield db_connection

    app.dependency_overrides[get_db_connection] = override_get_db

    try:
        # 1. Setup Data
        tenant_repo = TenantRepository(db_connection)

        # FIX: Added required admin fields to satisfy TenantCreate validation
        tenant = await tenant_repo.create(TenantCreate(
            name="Session Corp",
            plan="startup",
            admin_email="admin@session.com",  # <-- Added
            admin_password="password123",  # <-- Added
            admin_name="Session Admin"  # <-- Added
        ))

        user_repo = UserRepository(db_connection)
        await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))
        await user_repo.create_user(UserCreate(email="session@test.com", password="password123", display_name="User"))

        # 2. Login -> Get Refresh Token
        login_payload = {
            "email": "session@test.com", "password": "password123", "tenant_id": str(tenant.tenant_id)
        }
        resp_login = await async_client.post("/api/v1/auth/login", json=login_payload)
        assert resp_login.status_code == 200
        data = resp_login.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]

        assert len(refresh_token) > 20

        # 3. View Sessions
        headers = {"Authorization": f"Bearer {access_token}"}
        resp_sessions = await async_client.get("/api/v1/auth/sessions", headers=headers)
        assert resp_sessions.status_code == 200
        sessions = resp_sessions.json()
        assert len(sessions) == 1
        session_id = sessions[0]["session_id"]

        # 4. Use Refresh Token to get NEW Access Token
        resp_refresh = await async_client.post(f"/api/v1/auth/refresh?refresh_token={refresh_token}")
        assert resp_refresh.status_code == 200
        new_data = resp_refresh.json()
        assert new_data["access_token"] != access_token
        assert new_data["refresh_token"] != refresh_token  # Rotated

        # 5. Revoke Session
        resp_revoke = await async_client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
        assert resp_revoke.status_code == 204

        # 6. Verify Refresh Token Fails (Session Revoked)
        # We use the *new* refresh token from step 4
        new_refresh = new_data["refresh_token"]
        resp_fail = await async_client.post(f"/api/v1/auth/refresh?refresh_token={new_refresh}")
        assert resp_fail.status_code == 401  # Should fail because session is revoked

    finally:
        app.dependency_overrides.clear()