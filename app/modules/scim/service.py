from fastapi import HTTPException
from uuid import UUID
from app.modules.scim.repository import ScimRepository
from app.modules.scim.schemas import ScimUserCreate, ScimResponse
from app.modules.api_keys.repository import ApiKeyRepository
from app.core.security import verify_password  # used for checking API key hash


class ScimService:
    def __init__(self, scim_repo: ScimRepository, apikey_repo: ApiKeyRepository):
        self.repo = scim_repo
        self.apikey_repo = apikey_repo

    async def authenticate_scim_client(self, raw_api_key: str) -> UUID:
        """
        Validates the Bearer token (API Key) and returns the Tenant ID.
        SCIM clients send 'Authorization: Bearer pk_live_...'
        """
        if not raw_api_key.startswith("pk_live_"):
            raise HTTPException(401, "Invalid API Key format")

        prefix = raw_api_key[:8]
        record = await self.apikey_repo.get_key_by_prefix(prefix)

        if not record:
            raise HTTPException(401, "Invalid API Key")

        if not verify_password(raw_api_key, record['key_hash']):
            raise HTTPException(401, "Invalid API Key")

        if record['revoked']:
            raise HTTPException(401, "API Key revoked")

        # Optional: Check if key has 'scim.write' scope

        # Update last used
        await self.apikey_repo.update_last_used(record['api_key_id'])

        return record['tenant_id']

    async def create_user(self, raw_key: str, payload: ScimUserCreate):
        tenant_id = await self.authenticate_scim_client(raw_key)

        user_id = await self.repo.upsert_user(payload, tenant_id)

        # Construct SCIM Response
        return self._build_response(user_id, payload)

    def _build_response(self, user_id: UUID, payload: ScimUserCreate):
        return ScimResponse(
            id=str(user_id),
            userName=payload.userName,
            active=payload.active,
            meta={
                "resourceType": "User",
                "created": "2023-01-01T00:00:00Z",  # Simplified
                "location": f"/scim/v2/Users/{user_id}"
            }
        )