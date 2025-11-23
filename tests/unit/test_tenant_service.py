import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from fastapi import HTTPException
from uuid import uuid4
from app.modules.tenants.service import TenantService
from app.modules.tenants.schemas import TenantCreate, TenantOnboardingResponse


@pytest.mark.asyncio
async def test_onboard_tenant_domain_conflict():
    """
    Unit Test: Should raise 409 if repository says domain exists.
    """
    # 1. Mock Dependencies
    mock_tenant_repo = Mock()
    mock_user_repo = Mock()
    mock_role_repo = Mock()

    # 2. Configure Mock Behavior
    # Simulate "Domain already exists" -> returns a UUID
    mock_tenant_repo.get_by_domain = AsyncMock(return_value="existing-uuid")

    # 3. Initialize Service
    service = TenantService(mock_tenant_repo, mock_user_repo, mock_role_repo)

    # 4. Define Input
    payload = TenantCreate(
        name="Duplicate Firm",
        domain="exists.com",
        admin_email="admin@exists.com",
        admin_password="securepassword123",
        admin_name="Admin"
    )

    # 5. Assert Exception
    with pytest.raises(HTTPException) as exc:
        await service.onboard_tenant(payload)

    assert exc.value.status_code == 409
    assert "Domain already taken" in exc.value.detail

    # Verify we never tried to create anything
    mock_tenant_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_onboard_tenant_success():
    """
    Unit Test: Should verify orchestration logic (calls to all repos).
    """
    # 1. Mock Dependencies
    mock_tenant_repo = Mock()
    mock_user_repo = Mock()
    mock_role_repo = Mock()

    # --- FIX: Mock Transaction Context Manager Correctly ---
    mock_conn = Mock()
    mock_tenant_repo.conn = mock_conn

    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction

    # Setup Async Context Manager
    mock_transaction.__aenter__.return_value = None
    mock_transaction.__aexit__.return_value = None

    mock_conn.execute = AsyncMock()

    # Configure Success Responses
    mock_tenant_repo.get_by_domain = AsyncMock(return_value=None)

    # FIX: Use a valid UUID string for Pydantic validation
    valid_tenant_id = str(uuid4())

    # Mock Tenant Response Object
    mock_tenant = Mock()
    mock_tenant.tenant_id = valid_tenant_id

    # Service calls model_dump() to construct response
    # Must return valid UUID here too
    mock_tenant.model_dump.return_value = {
        "tenant_id": valid_tenant_id,
        "name": "New Firm",
        "status": "active",
        "created_at": "2023-01-01"
    }
    mock_tenant_repo.create = AsyncMock(return_value=mock_tenant)

    # Mock Role Response
    mock_role = Mock()
    mock_role.role_id = str(uuid4())
    mock_role_repo.create_role = AsyncMock(return_value=mock_role)

    # Mock User Response
    mock_user = Mock()
    mock_user.user_id = str(uuid4())
    mock_user.email = "admin@new.com"
    mock_user_repo.create_user = AsyncMock(return_value=mock_user)

    # 2. Init Service
    service = TenantService(mock_tenant_repo, mock_user_repo, mock_role_repo)

    # 3. Act
    payload = TenantCreate(
        name="New Firm",
        domain="new.com",
        admin_email="admin@new.com",
        admin_password="securepassword123",
        admin_name="Admin"
    )
    result = await service.onboard_tenant(payload)

    # 4. Assert
    assert isinstance(result, TenantOnboardingResponse)
    assert result.admin_email == "admin@new.com"
    assert str(result.tenant_id) == valid_tenant_id

    # Verify Logic Flow
    mock_tenant_repo.create.assert_called_once_with(payload)
    mock_role_repo.create_role.assert_called_once()

    # Verify User Creation passes the specific tenant_id
    mock_user_repo.create_user.assert_called_once()
    call_kwargs = mock_user_repo.create_user.call_args.kwargs
    assert call_kwargs['tenant_id'] == valid_tenant_id

    # Verify Role Assignment Query executed via conn.execute
    assert mock_conn.execute.call_count >= 1