# app/modules/system/service.py

from app.modules.system.repository import SystemRepository
from app.modules.system.schemas import CleanupResult


class SystemService:
    """
    Orchestrates system-level maintenance tasks.
    """

    def __init__(self, conn) -> None:
        self.conn = conn
        self.repo = SystemRepository(conn)

    async def run_cleanup(self) -> CleanupResult:
        """
        Runs all cleanup routines and returns a summary.
        """
        expired_tokens = await self.repo.cleanup_expired_refresh_tokens()
        expired_password_tokens = await self.repo.cleanup_expired_password_reset_tokens()
        expired_blacklist = await self.repo.cleanup_expired_blacklist_entries()

        return CleanupResult(
            expired_tokens_deleted=expired_tokens,
            expired_password_tokens_deleted=expired_password_tokens,
            expired_blacklist_entries_deleted=expired_blacklist,
            message="Cleanup completed successfully",
        )
