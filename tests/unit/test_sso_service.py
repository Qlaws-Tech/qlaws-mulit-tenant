# tests/unit/test_sso_service.py

import pytest
from unittest.mock import Mock, AsyncMock

from uuid import uuid4

from app.modules.sso.service import SSOService
from app.modules.sso.schemas import SSOProviderCreate


@pytest.mark.asyncio
async def test_sso_create_masks_only_on_list():
    conn = Mock()
    repo = Mock()
    audit = Mock()

    # Wire up mocked repo into service
    svc = SSOService(conn)
    svc.repo = repo
    svc.audit_repo = audit

    provider_id = uuid4()
    created = Mock()
    created.sso_provider_id = provider_id
    created.provider_type = "oidc"
    created.name = "Corporate Okta"
    created.description = "Main"
    created.enabled = True
    created.config = {
        "client_id": "okta_123",
        "client_secret": "SUPER_SECRET_VALUE_123",
        "issuer_url": "https://okta.com/tenant",
    }
    created.created_at = "2024-01-01T00:00:00Z"

    repo.create = AsyncMock(return_value=created)
    repo.list_providers = AsyncMock(return_value=[created])

    payload = SSOProviderCreate(
        provider_type="oidc",
        name="Corporate Okta",
        description="Main",
        enabled=True,
        config=created.config,
    )

    # Create → should return plaintext
    out = await svc.create_provider(payload)
    assert out.config["client_secret"] == "SUPER_SECRET_VALUE_123"

    # List → should return masked
    listed = await svc.list_providers()
    assert listed[0].config["client_secret"] == "********"
