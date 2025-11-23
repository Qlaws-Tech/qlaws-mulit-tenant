from asyncpg import Connection
from app.modules.sso.schemas import SsoProviderCreate, SsoProviderResponse
from uuid import UUID
import json


class SsoRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(self, data: SsoProviderCreate, encrypted_config: dict) -> SsoProviderResponse:
        query = """
            INSERT INTO sso_providers (
                tenant_id, 
                provider_type, 
                name, 
                config, 
                is_default, 
                enabled
            )
            VALUES (
                current_setting('app.current_tenant_id')::uuid, 
                $1, $2, $3, $4, true
            )
            RETURNING sso_id, provider_type, name, config, enabled, created_at, is_default
        """

        row = await self.conn.fetchrow(
            query,
            data.provider_type,
            data.name,
            json.dumps(encrypted_config),
            data.is_default
        )

        return self._map_row(row)

    async def list_providers(self) -> list[SsoProviderResponse]:
        query = """
            SELECT sso_id, provider_type, name, config, enabled, created_at
            FROM sso_providers
        """
        rows = await self.conn.fetch(query)
        return [self._map_row(row) for row in rows]

    def _map_row(self, row) -> SsoProviderResponse:
        """Helper to safely handle JSON parsing from DB rows"""
        data = dict(row)
        # asyncpg might return 'config' as a string (JSON), but Pydantic wants a Dict.
        if isinstance(data.get('config'), str):
            data['config'] = json.loads(data['config'])
        return SsoProviderResponse(**data)