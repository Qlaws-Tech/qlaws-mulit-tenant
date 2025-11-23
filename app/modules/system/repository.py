from asyncpg import Connection
from app.modules.system.schemas import CleanupResult

class SystemRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def cleanup_audit_logs(self, retention_days: int) -> int:
        """
        Deletes audit logs older than retention policy.
        Note: On massive tables, DROP PARTITION is better, but DELETE is fine for MVP.
        """
        query = """
            DELETE FROM audit_logs 
            WHERE event_time < now() - ($1 || ' days')::interval
        """
        # execute returns "DELETE <count>"
        result = await self.conn.execute(query, str(retention_days))
        return self._parse_count(result)

    async def cleanup_expired_tokens(self) -> int:
        """
        Removes refresh tokens that are expired.
        """
        query = "DELETE FROM refresh_tokens WHERE expires_at < now()"
        result = await self.conn.execute(query)
        return self._parse_count(result)

    async def cleanup_revoked_tokens(self, retention_days: int) -> int:
        """
        Removes blacklisted JTI records older than X days.
        """
        query = """
            DELETE FROM token_blacklist 
            WHERE revoked_at < now() - ($1 || ' days')::interval
        """
        result = await self.conn.execute(query, str(retention_days))
        return self._parse_count(result)

    def _parse_count(self, command_tag: str) -> int:
        # Format is usually "DELETE 123"
        try:
            return int(command_tag.split(" ")[1])
        except:
            return 0