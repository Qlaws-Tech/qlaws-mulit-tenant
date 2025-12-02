# tests/unit/test_tenant_service.py

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from fastapi import HTTPException
from uuid import uuid4

from app.modules.tenants.service import TenantService
from app.modules.tenants.schemas import TenantCreate, TenantOnboardingResponse


@pytest.mark.asyncio
async def test_onboard_tenant_domain_conflict():
    mock_tenant_repo = Mock()
    mock_user_repo = Mock()
    mock_role_repo = Mock()

    mock_tenant_repo.get_by_domain = AsyncMock(return_value="existing-tenant")

    service = TenantService(mock_tenant_repo, mock_user_repo, mock_role_repo)

    payload = TenantCreate(
        name="Duplicate Firm",
        domain="exists.com",
        plan="startup",
        region="us-east-1",
        admin_email="admin@exists.com",
        admin_password="securepassword123",
        admin_name="Admin"
    )

    with pytest.raises(HTTPException) as exc:
        await service.onboard_tenant(payload)

    assert exc.value.status_code == 409
    assert "Domain already taken" in exc.value.detail
    mock_tenant_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_onboard_tenant_success():
    mock_tenant_repo = Mock()
    mock_user_repo = Mock()
    mock_role_repo = Mock()

    # fake connection + transaction for service
    mock_conn = Mock()
    mock_tenant_repo.conn = mock_conn
    mock_tr = MagicMock()
    mock_conn.transaction.return_value = mock_tr
    mock_tr.__aenter__.return_value = None
    mock_tr.__aexit__.return_value = None

    mock_conn.execute = AsyncMock()

    mock_tenant_repo.get_by_domain = AsyncMock(return_value=None)

    # Valid IDs
    tenant_id = uuid4()
    role_id = uuid4()
    user_id = uuid4()

    # Tenant
    mock_tenant = Mock()
    mock_tenant.tenant_id = tenant_id
    mock_tenant.name = "New Firm"
    mock_tenant.domain = "new.com"
    mock_tenant.plan = "startup"
    mock_tenant.region = "us-east-1"
    mock_tenant.status = "active"
    mock_tenant.created_at = "2023-01-01T00:00:00Z"

    mock_tenant_repo.create = AsyncMock(return_value=mock_tenant)

    # Role
    mock_role = Mock()
    mock_role.role_id = role_id
    mock_role_repo.create_role = AsyncMock(return_value=mock_role)

    # User
    mock_user = Mock()
    mock_user.user_id = user_id
    mock_user.email = "admin@new.com"
    mock_user_repo.create_user = AsyncMock(return_value=mock_user)

    service = TenantService(mock_tenant_repo, mock_user_repo, mock_role_repo)

    payload = TenantCreate(
        name="New Firm",
        domain="new.com",
        plan="startup",
        region="us-east-1",
        admin_email="admin@new.com",
        admin_password="securepassword123",
        admin_name="Admin",
    )

    result = await service.onboard_tenant(payload)

    assert isinstance(result, TenantOnboardingResponse)
    assert result.admin_email == "admin@new.com"
    assert str(result.tenant_id) == str(tenant_id)

    mock_tenant_repo.create.assert_called_once()
    mock_role_repo.create_role.assert_called_once()
    mock_user_repo.create_user.assert_called_once()
    assert mock_conn.execute.call_count >= 1
