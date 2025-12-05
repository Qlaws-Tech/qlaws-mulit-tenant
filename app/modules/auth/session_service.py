# app/modules/auth/session_service.py

from uuid import uuid4
from datetime import datetime
from asyncpg import Connection


class SessionService:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create_session(self, user_id: str, tenant_id: str, ip: str):
        row = await self.conn.fetchrow(
            """
            INSERT INTO sessions (session_id, user_tenant_id, tenant_id, ip_address)
            VALUES ($1,
                (SELECT user_tenant_id FROM user_tenants WHERE user_id = $2 AND tenant_id = $3),
                $3,
                $4
            )
            RETURNING *
            """,
            str(uuid4()), user_id, tenant_id, ip
        )
        return row

    async def store_refresh_token(self, session_id: str, token: str):
        token_hash = await self._hash(token)
        expires = datetime.utcnow()
        await self.conn.execute(
            """
            INSERT INTO refresh_tokens (session_id, token_hash, expires_at)
            VALUES ($1, $2, now() + interval '30 days')
            """,
            session_id, token_hash
        )

    async def get_session(self, session_id: str):
        return await self.conn.fetchrow(
            "SELECT * FROM sessions WHERE session_id = $1",
            session_id
        )

    async def revoke_session(self, session_id: str):
        await self.conn.execute(
            "DELETE FROM sessions WHERE session_id = $1",
            session_id
        )

    async def rotate_refresh_token(self, session_id: str, new_token: str):
        token_hash = await self._hash(new_token)
        await self.conn.execute(
            """
            UPDATE refresh_tokens
            SET token_hash = $2, expires_at = now() + interval '30 days'
            WHERE session_id = $1
            """,
            session_id, token_hash
        )

    async def _hash(self, token):
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()
