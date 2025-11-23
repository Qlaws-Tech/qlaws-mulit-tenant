from asyncpg import Connection
from app.modules.auth.mfa.schemas import MfaMethodResponse
from uuid import UUID
import json


class MfaRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create_totp_method(self, user_id: str, secret: str, tenant_id: str):
        """
        Stores the TOTP secret.
        """
        # FIX: Explicitly cast string inputs to UUID in SQL
        query = """
            INSERT INTO mfa_methods (user_id, tenant_id, method_type, metadata, enabled)
            VALUES ($1::uuid, $2::uuid, 'totp', $3::jsonb, false)
            RETURNING mfa_id, method_type, enabled, created_at
        """

        # FIX: Dump dictionary to JSON string for 'jsonb' column
        metadata = json.dumps({"secret": secret})

        # Ensure we pass strings to asyncpg when using ::uuid cast
        row = await self.conn.fetchrow(query, str(user_id), str(tenant_id), metadata)
        return MfaMethodResponse(**dict(row))

    async def enable_method(self, mfa_id: UUID):
        query = """
            UPDATE mfa_methods 
            SET enabled = true 
            WHERE mfa_id = $1
            RETURNING mfa_id, method_type, enabled, created_at
        """
        row = await self.conn.fetchrow(query, mfa_id)
        return MfaMethodResponse(**dict(row))

    async def get_active_method(self, user_id: str):
        query = """
            SELECT mfa_id, method_type, metadata, enabled, created_at
            FROM mfa_methods
            WHERE user_id = $1::uuid AND enabled = true AND method_type = 'totp'
            LIMIT 1
        """
        return await self.conn.fetchrow(query, str(user_id))