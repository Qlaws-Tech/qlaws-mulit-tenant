import pytest
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate, RoleUpdate


@pytest.mark.asyncio
async def test_role_crud_operations(db_connection):
    """
    1. Setup Tenant.
    2. Create Role with Permissions.
    3. Update Role.
    4. Verify RLS (Another tenant shouldn't see it).
    """
    # 1. Setup Context
    tenant_repo = TenantRepository(db_connection)

    # FIX: Added required admin fields to satisfy TenantCreate validation
    tenant = await tenant_repo.create(TenantCreate(
        name="Law Firm A",
        plan="startup",
        admin_email="admin@firm-a.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Admin A"  # <-- Added
    ))

    # Manually set RLS context for the test
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

    # 2. Create Role
    role_repo = RoleRepository(db_connection)

    # Seed permissions first (normally done via migration)
    await db_connection.execute(
        "INSERT INTO permissions (key, description) VALUES ('case.view', 'View Cases'), ('case.edit', 'Edit Cases') ON CONFLICT DO NOTHING"
    )

    new_role = await role_repo.create_role(RoleCreate(
        name="Senior Associate",
        description="Handles complex cases",
        permission_keys=["case.view", "case.edit"]
    ))

    assert new_role.name == "Senior Associate"
    assert "case.view" in new_role.permissions
    assert len(new_role.permissions) == 2

    # 3. Update Role (Remove one permission)
    updated_role = await role_repo.update_role(
        new_role.role_id,
        RoleUpdate(name="Lead Associate", permission_keys=["case.view"])  # removing case.edit
    )

    assert updated_role.name == "Lead Associate"
    assert len(updated_role.permissions) == 1
    assert "case.edit" not in updated_role.permissions

    # 4. Verify RLS Isolation
    # Create Tenant B
    # FIX: Added required admin fields for Tenant B as well
    tenant_b = await tenant_repo.create(TenantCreate(
        name="Law Firm B",
        plan="startup",
        admin_email="admin@firm-b.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Admin B"  # <-- Added
    ))

    # Switch Context
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b.tenant_id))

    # Try to fetch roles
    roles_b = await role_repo.get_roles()
    assert len(roles_b) == 0  # Should not see Firm A's roles