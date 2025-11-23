import pytest
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate
from app.modules.groups.repository import GroupRepository
from app.modules.groups.schemas import GroupCreate


@pytest.mark.asyncio
async def test_groups_management(db_connection):
    # 1. Setup Tenant
    tenant_repo = TenantRepository(db_connection)

    # FIX: Added required admin fields to satisfy TenantCreate schema validation
    tenant = await tenant_repo.create(TenantCreate(
        name="Group Corp",
        plan="enterprise",
        admin_email="admin@groups.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Group Admin"  # <-- Added
    ))

    # Set Context
    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant.tenant_id))

    # 2. Setup User
    user_repo = UserRepository(db_connection)

    # Create User (Password length >= 8 chars)
    user = await user_repo.create_user(UserCreate(
        email="employee@g.com",
        password="password123",
        display_name="Emp"
    ))

    # 3. Create Group
    group_repo = GroupRepository(db_connection)
    group = await group_repo.create(GroupCreate(name="Engineering", description="Dev Team"))

    assert group.name == "Engineering"

    # 4. Add Member
    success = await group_repo.add_member(group.group_id, user.user_id)
    assert success is True

    # 5. Verify List
    groups = await group_repo.list_groups()
    assert len(groups) == 1
    assert groups[0].member_count == 1

    # 6. RLS Check (Switch Tenant)
    # Create Tenant B (Also needs admin fields)
    tenant_b = await tenant_repo.create(TenantCreate(
        name="Other Corp",
        plan="startup",
        admin_email="admin@other.com",  # <-- Added
        admin_password="password123",  # <-- Added
        admin_name="Other Admin"  # <-- Added
    ))

    await db_connection.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_b.tenant_id))

    groups_b = await group_repo.list_groups()
    assert len(groups_b) == 0  # Should not see "Engineering"