# app/modules/auth/repository.py
from datetime import datetime
from uuid import UUID
from typing import Optional

from asyncpg import Connection

from app.modules.users.schemas import UserResponse


class AuthRepository:
    """
    Low-level queries for login and user lookup.
    """

    def __init__(self, conn: Connection):
        # just store the connection; do NOT create another AuthRepository here
        self.conn = conn


    async def get_user_by_email(self, email: str) -> UserResponse | None:
        row = await self.conn.fetchrow(
            """
            SELECT user_id, primary_email AS email, display_name, created_at
            FROM users
            WHERE primary_email = $1
            """,
            email.lower()
        )
        return UserResponse(**row) if row else None

    async def update_last_seen(self, session_id: UUID):
        await self.conn.execute(
            """
            UPDATE sessions
            SET last_seen_at = $1
            WHERE session_id = $2
            """,
            datetime.utcnow(),
            session_id
        )

    async def get_user_for_login(
        self,
        tenant_id: UUID,
        email: str,
    ) -> Optional[dict]:
        """
        Look up a user joined with user_tenants for a given tenant and email.

        - Uses users.primary_email and users.hashed_password
        - Filters by user_tenants.tenant_id
        - RLS on user_tenants requires current_setting('app.current_tenant_id')
          to match this tenant_id, so the caller must set it.
        """
        row = await self.conn.fetchrow(
            """
            SELECT
                u.user_id,
                u.primary_email,
                u.hashed_password,
                ut.user_tenant_id,
                ut.status
            FROM users u
            JOIN user_tenants ut ON ut.user_id = u.user_id
            WHERE lower(u.primary_email) = lower($1)
              AND ut.tenant_id = $2::uuid
            """,
            email,
            str(tenant_id),
        )
        return dict(row) if row else None
