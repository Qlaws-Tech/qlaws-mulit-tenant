# app/modules/auth/session_repository.py

"""
SessionRepository handles pure session operations.
Separation of concerns from AuthRepository keeps logic cleaner.
"""

from uuid import UUID
from asyncpg import Connection
from typing import Optional


class SessionRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # --------------------------------------------------
    # Fetch user_tenant_id → needed for session ops
    # --------------------------------------------------
    async def get_user_tenant_id(self, user_id: UUID, tenant_id: UUID) -> Optional[UUID]:
        """
        Return user_tenant_id for a given user/tenant pair.
        Required for listing sessions and creating them.
        """
        row = await self.conn.fetchrow(
            """
            SELECT user_tenant_id
            FROM user_tenants
            WHERE user_id = $1 AND tenant_id = $2
            """,
            user_id,
            tenant_id
        )
        return row["user_tenant_id"] if row else None

    # --------------------------------------------------
    # List sessions
    # --------------------------------------------------
    async def list_sessions(self, user_tenant_id: UUID):
        """
        Returns all sessions for a user under a tenant.
        """
        return await self.conn.fetch(
            """
            SELECT session_id, ip_address, created_at, last_seen_at
            FROM sessions
            WHERE user_tenant_id = $1
            ORDER BY created_at DESC
            """,
            user_tenant_id
        )

    # --------------------------------------------------
    # Revoke (delete) a session
    # --------------------------------------------------
    async def revoke_session(self, session_id: UUID):
        await self.conn.execute(
            "DELETE FROM sessions WHERE session_id = $1",
            session_id
        )

    # --------------------------------------------------
    # Revoke all user sessions
    # --------------------------------------------------
    async def revoke_all_user_sessions(self, user_tenant_id: UUID):
        await self.conn.execute(
            """
            DELETE FROM sessions
            WHERE user_tenant_id = $1
            """,
            user_tenant_id
        )
