# app/modules/system/repository.py

from asyncpg import Connection


class SystemRepository:
    """
    Low-level cleanup repository.

    Performs cross-tenant maintenance:
    - Deletes expired refresh tokens
    - Deletes expired password reset tokens
    - Deletes expired blacklist entries
    """

    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    async def cleanup_expired_refresh_tokens(self) -> int:
        """
        Deletes rows in refresh_tokens where expires_at < now().

        Returns: number of rows deleted.
        """
        result = await self.conn.execute(
            "DELETE FROM refresh_tokens WHERE expires_at < now()"
        )
        # asyncpg returns e.g. "DELETE 3"
        try:
            return int(result.split()[-1])
        except Exception:
            return 0

    async def cleanup_expired_password_reset_tokens(self) -> int:
        result = await self.conn.execute(
            "DELETE FROM password_reset_tokens WHERE expires_at < now()"
        )
        try:
            return int(result.split()[-1])
        except Exception:
            return 0

    async def cleanup_expired_blacklist_entries(self) -> int:
        result = await self.conn.execute(
            "DELETE FROM token_blacklist WHERE expires_at < now()"
        )
        try:
            return int(result.split()[-1])
        except Exception:
            return 0
