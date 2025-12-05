# app/modules/auth/password_reset_repository.py

"""
Repository for secure password reset operations.
- Create hashed reset token
- Look up user by hashed token
- Expire token
"""

from uuid import UUID
from datetime import datetime
from asyncpg import Connection
from typing import Optional


class PasswordResetRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # --------------------------------------------------
    # Store reset token (hashed)
    # --------------------------------------------------
    async def store_reset_token(self, user_id: UUID, token_hash: str, expires_at: datetime):
        await self.conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id,
            token_hash,
            expires_at
        )

    # --------------------------------------------------
    # Resolve user by token hash
    # --------------------------------------------------
    async def get_user_by_token(self, token_hash: str) -> Optional[UUID]:
        row = await self.conn.fetchrow(
            """
            SELECT user_id
            FROM password_reset_tokens
            WHERE token_hash = $1
              AND expires_at > now()
            """,
            token_hash
        )
        return row["user_id"] if row else None

    # --------------------------------------------------
    # Delete reset token (prevent reuse)
    # --------------------------------------------------
    async def delete_token(self, token_hash: str):
        await self.conn.execute(
            "DELETE FROM password_reset_tokens WHERE token_hash = $1",
            token_hash
        )

    # --------------------------------------------------
    # Cleanup expired tokens
    # --------------------------------------------------
    async def cleanup_expired(self):
        await self.conn.execute(
            "DELETE FROM password_reset_tokens WHERE expires_at < now()"
        )
