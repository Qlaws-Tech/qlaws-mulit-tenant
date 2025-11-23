import secrets
from datetime import datetime, timedelta, timezone
from app.core.security import get_password_hash
from app.modules.api_keys.repository import ApiKeyRepository
from app.modules.api_keys.schemas import ApiKeyCreate, ApiKeyCreatedResponse


class ApiKeyService:
    def __init__(self, repo: ApiKeyRepository):
        self.repo = repo

    async def create_api_key(self, data: ApiKeyCreate) -> ApiKeyCreatedResponse:
        # 1. Generate Secure Random Key
        # Format: "pk_live_" + 32 random hex chars
        raw_key = f"pk_live_{secrets.token_urlsafe(32)}"

        # 2. Hash it (One-way)
        key_hash = get_password_hash(raw_key)

        # 3. Extract Prefix (for DB lookup)
        prefix = raw_key[:8]  # e.g., "pk_live_" + first few chars

        # 4. Calculate Expiry
        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

        # 5. Save
        record = await self.repo.create(
            data.name, key_hash, prefix, data.scopes, expires_at
        )

        # 6. Return Plain Key (ONCE)
        return ApiKeyCreatedResponse(**record, plain_key=raw_key)

    async def list_keys(self):
        return await self.repo.list_keys()

    async def revoke_key(self, key_id):
        await self.repo.revoke(key_id)