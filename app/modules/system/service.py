from app.modules.system.repository import SystemRepository
from app.modules.system.schemas import CleanupResult


class SystemService:
    def __init__(self, repo: SystemRepository):
        self.repo = repo

    async def run_nightly_cleanup(self) -> CleanupResult:
        # 1. Audit Logs: Keep 90 days (Standard compliance)
        audit_count = await self.repo.cleanup_audit_logs(retention_days=90)

        # 2. Expired Refresh Tokens: Delete immediately (Useless data)
        token_count = await self.repo.cleanup_expired_tokens()

        # 3. Blacklist: Keep 7 days (Matches max access token lifetime usually)
        #    If an access token lives 30 mins, keeping blacklist for 7 days is safe.
        blacklist_count = await self.repo.cleanup_revoked_tokens(retention_days=7)

        return CleanupResult(
            audit_logs_deleted=audit_count,
            expired_tokens_deleted=token_count,
            revoked_tokens_deleted=blacklist_count,
            message="Cleanup completed successfully"
        )