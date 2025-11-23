import pytest
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_rls_isolation(db_connection):
    """
    CRITICAL SECURITY TEST:
    1. Create Tenant A and Tenant B.
    2. Create User A (linked to Tenant A).
    3. Create User B (linked to Tenant B).
    4. Set Context to Tenant A -> Should ONLY see User A.
    5. Set Context to Tenant B -> Should ONLY see User B.
    """
    # 1. Setup Tenants
    tenant_repo = TenantRepository(db_connection)

    # FIX: Added required admin fields for Tenant A
    tenant_a = await tenant_repo.create(TenantCreate(
        name="Tenant A",
        plan="startup",
        admin_email="admin@a.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Admin A"  # <-- Added
    ))

    # FIX: Added required admin fields for Tenant B
    tenant_b = await tenant_repo.create(TenantCreate(
        name="Tenant B",
        plan="startup",
        admin_email="admin@b.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Admin B"  # <-- Added
    ))

    # 2. Setup Users (Manually switching context for setup)
    user_repo = UserRepository(db_connection)

    # Create User for Tenant A
    # Note: We manually create the user here to control the exact email/name for testing isolation
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_a.tenant_id))
    await user_repo.create_user(UserCreate(
        email="alice@tenant-a.com", password="password123", display_name="Alice"
    ))

    # Create User for Tenant B
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b.tenant_id))
    await user_repo.create_user(UserCreate(
        email="bob@tenant-b.com", password="password123", display_name="Bob"
    ))

    # 3. VERIFY TENANT A CONTEXT
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_a.tenant_id))
    users_a = await user_repo.get_users_by_tenant()

    print(f"\nTenant A sees: {[u.email for u in users_a]}")
    # Should see Alice (created manually) AND Admin A (created via onboarding if repo logic runs fully,
    # but repo.create only makes tenant row. user_repo.create made Alice.
    # So count depends on if repo.create() logic was updated to insert user too or if that is Service layer logic.
    # Based on our repo code, repo.create ONLY inserts tenant. So we expect only Alice.)

    # Check if Alice is present
    emails_a = [u.email for u in users_a]
    assert "alice@tenant-a.com" in emails_a
    assert "bob@tenant-b.com" not in emails_a

    # 4. VERIFY TENANT B CONTEXT
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b.tenant_id))
    users_b = await user_repo.get_users_by_tenant()

    print(f"Tenant B sees: {[u.email for u in users_b]}")
    emails_b = [u.email for u in users_b]
    assert "bob@tenant-b.com" in emails_b
    assert "alice@tenant-a.com" not in emails_b