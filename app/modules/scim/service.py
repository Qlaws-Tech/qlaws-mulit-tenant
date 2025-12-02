# app/modules/scim/service.py

from uuid import UUID
from fastapi import HTTPException, status
from starlette.requests import Request

from app.modules.scim.schemas import SCIMUserCreate, SCIMUserResponse
from app.modules.scim.repository import SCIMRepository
from app.modules.api_keys.service import ApiKeyService
from app.modules.api_keys.repository import ApiKeyRepository


class SCIMService:
    """
    SCIM 2.0 service layer.

    - Authenticates API key (Okta, Entra, etc.) using scim.write scope.
    - Provisions users into the tenant associated with the API key.
    """

    def __init__(self, conn):
        self.conn = conn
        self.repo = SCIMRepository(conn)
        self.api_key_service = ApiKeyService(ApiKeyRepository(conn))

    async def _authenticate_scim_request(self, auth_header: str) -> UUID:
        """
        Parses Authorization: Bearer <token> and validates via API key service.
        Requires 'scim.write' scope.
        Returns tenant_id of the key.
        """
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing SCIM bearer token")

        token = auth_header.split(" ", 1)[1].strip()
        key_info = await self.api_key_service.validate_token(token, required_scope="scim.write")

        if not key_info:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid SCIM token")

        return key_info.tenant_id

    async def create_scim_user(
        self,
        request: Request,
        payload: SCIMUserCreate,
        authorization: str,
    ) -> SCIMUserResponse:
        # 1. Auth via API key
        tenant_id = await self._authenticate_scim_request(authorization)

        # NOTE:
        # RLS: The connection used here should already have current_setting('app.current_tenant_id')
        # set in tests via dependency override.
        # For general runtime, you could add a dedicated SCIM DB dependency that sets it from tenant_id.

        # 2. Provision user
        base_url = str(request.base_url).rstrip("/")
        return await self.repo.create_scim_user(payload, tenant_id, base_url)
