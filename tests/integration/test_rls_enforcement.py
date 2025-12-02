# tests/integration/test_rls_enforcement.py

import pytest

from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_rls_isolation(db_connection):
    tenant_repo = TenantRepository(db_connection)

    tenant_a = await tenant_repo.create(
        TenantCreate(
            name="Tenant A",
            plan="startup",
            admin_email="admin@a.com",
            admin_password="password123",
            admin_name="Admin A",
        )
    )

    tenant_b = await tenant_repo.create(
        TenantCreate(
            name="Tenant B",
            plan="startup",
            admin_email="admin@b.com",
            admin_password="password123",
            admin_name="Admin B",
        )
    )

    user_repo = UserRepository(db_connection)

    # Create user for Tenant A
    await db_connection.execute(
        "SELECT set_config('app.current_tenant_id', $1, true)",
        str(tenant_a.tenant_id),
    )
    await user_repo.create_user(
        UserCreate(
            email="alice@tenant-a.com",
            password="password123",
            display_name="Alice",
        )
    )

    # Create user for Tenant B
    await db_connection.execute(
        "SELECT set_config('app.current_tenant_id', $1, true)",
        str(tenant_b.tenant_id),
    )
    await user_repo.create_user(
        UserCreate(
            email="bob@tenant-b.com",
            password="password123",
            display_name="Bob",
        )
    )

    # Verify Tenant A context
    await db_connection.execute(
        "SELECT set_config('app.current_tenant_id', $1, true)",
        str(tenant_a.tenant_id),
    )
    users_a = await user_repo.get_users_by_tenant()
    emails_a = [u.email for u in users_a]
    assert "alice@tenant-a.com" in emails_a
    assert "bob@tenant-b.com" not in emails_a

    # Verify Tenant B context
    await db_connection.execute(
        "SELECT set_config('app.current_tenant_id', $1, true)",
        str(tenant_b.tenant_id),
    )
    users_b = await user_repo.get_users_by_tenant()
    emails_b = [u.email for u in users_b]
    assert "bob@tenant-b.com" in emails_b
    assert "alice@tenant-a.com" not in emails_b
