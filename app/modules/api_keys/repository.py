# app/modules/api_keys/repository.py

from typing import List, Optional
from uuid import UUID

from asyncpg import Connection

from app.modules.api_keys.schemas import ApiKeyResponse, ApiKeyInfo


class ApiKeyRepository:
    """
    Tenant-scoped API key repository.

    Table: api_keys
      - api_key_id UUID
      - tenant_id UUID
      - name TEXT
      - hashed_key TEXT
      - scopes TEXT[]
      - created_at TIMESTAMPTZ
    """

    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(
        self,
        name: str,
        hashed_key: str,
        scopes: list[str],
    ) -> ApiKeyResponse:
        row = await self.conn.fetchrow(
            """
            INSERT INTO api_keys (
                api_key_id,
                tenant_id,
                name,
                hashed_key,
                scopes
            )
            VALUES (
                uuid_generate_v4(),
                current_setting('app.current_tenant_id', true)::uuid,
                $1,
                $2,
                $3::text[]
            )
            RETURNING api_key_id, name, scopes, created_at
            """,
            name,
            hashed_key,
            scopes,
        )
        return ApiKeyResponse(**row)

    async def list_keys(self) -> List[ApiKeyResponse]:
        rows = await self.conn.fetch(
            """
            SELECT api_key_id, name, scopes, created_at
            FROM api_keys
            ORDER BY created_at DESC
            """
        )
        return [ApiKeyResponse(**r) for r in rows]

    async def delete(self, api_key_id: UUID) -> None:
        await self.conn.execute(
            "DELETE FROM api_keys WHERE api_key_id = $1",
            api_key_id,
        )

    async def get_by_hashed_key(self, hashed_key: str) -> Optional[ApiKeyInfo]:
        row = await self.conn.fetchrow(
            """
            SELECT api_key_id, tenant_id, scopes
            FROM api_keys
            WHERE hashed_key = $1
            """,
            hashed_key,
        )
        return ApiKeyInfo(**row) if row else None
