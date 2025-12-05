# tests/unit/test_scim_service.py

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from starlette.requests import Request
from starlette.datastructures import URL

from app.modules.scim.service import SCIMService
from app.modules.scim.schemas import SCIMUserCreate, SCIMName, SCIMEmail


@pytest.mark.asyncio
async def test_scim_service_provisions_user():
    conn = Mock()

    svc = SCIMService(conn)
    svc._authenticate_scim_request = AsyncMock(return_value=uuid4())

    user_repo = Mock()
    scim_repo = Mock()
    svc.repo = scim_repo

    scim_resp = Mock()
    scim_repo.create_scim_user = AsyncMock(return_value=scim_resp)

    scope = {"type": "http", "path": "/scim/v2/Users", "headers": []}
    request = Request(scope)
    request._url = URL("https://example.com/")

    payload = SCIMUserCreate(
        schemas=["urn:ietf:params:scim:schemas:core:2.0:User"],
        userName="user@example.com",
        name=SCIMName(givenName="Test", familyName="User"),
        emails=[SCIMEmail(value="user@example.com", primary=True)],
        active=True,
    )

    out = await svc.create_scim_user(request, payload, "Bearer xyz")
    scim_repo.create_scim_user.assert_awaited()
    assert out is scim_resp
