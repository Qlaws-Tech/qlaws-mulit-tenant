from asyncpg import Connection
from datetime import datetime
from uuid import UUID
from typing import List
from app.modules.api_keys.schemas import ApiKeyResponse

class ApiKeyRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(self, name: str, key_hash: str, prefix: str, scopes: list, expires_at: datetime) -> dict:
        """
        Inserts the hashed key.
        """
        query = """
            INSERT INTO api_keys (
                tenant_id, 
                name, 
                key_hash, 
                prefix, 
                scopes, 
                expires_at,
                created_at
            )
            VALUES (
                current_setting('app.current_tenant_id')::uuid, 
                $1, $2, $3, $4, $5, now()
            )
            RETURNING api_key_id, name, prefix, scopes, last_used_at, expires_at, created_at
        """
        row = await self.conn.fetchrow(query, name, key_hash, prefix, scopes, expires_at)
        return dict(row)

    async def list_keys(self) -> List[ApiKeyResponse]:
        query = """
            SELECT api_key_id, name, prefix, scopes, last_used_at, expires_at, created_at
            FROM api_keys
            WHERE revoked = false
            ORDER BY created_at DESC
        """
        rows = await self.conn.fetch(query)
        return [ApiKeyResponse(**dict(row)) for row in rows]

    async def revoke(self, api_key_id: UUID):
        """Soft deletes the key."""
        await self.conn.execute(
            "UPDATE api_keys SET revoked = true WHERE api_key_id = $1",
            api_key_id
        )

    async def get_key_by_prefix(self, prefix: str):
        """
        Used for Authentication.
        Fetches the hash based on the prefix (optimization to avoid checking every row).
        Note: This query likely runs WITHOUT RLS context initially (system lookup),
        or we must pass tenant_id if we know it.
        """
        # In a secure design, we look up by prefix globally, verify hash,
        # THEN enforce tenant context.
        query = """
            SELECT api_key_id, tenant_id, key_hash, scopes, expires_at, revoked
            FROM api_keys
            WHERE prefix = $1
        """
        return await self.conn.fetchrow(query, prefix)

    async def update_last_used(self, api_key_id: UUID):
        await self.conn.execute(
            "UPDATE api_keys SET last_used_at = now() WHERE api_key_id = $1",
            api_key_id
        )