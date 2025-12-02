# app/modules/audit/service.py

from uuid import UUID

from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditQuery, AuditLogResponse, AuditLogCreate


class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def log(
        self,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        action_type: str,
        resource_type: str,
        resource_id: str | None,
        ip_address: str | None,
        details: dict,
    ) -> None:
        """
        Logs an event.
        Note: 'tenant_id' is passed here for interface consistency but the
        Repository uses the active DB connection's RLS setting.
        """
        # 1. Construct the payload schema
        payload = AuditLogCreate(
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id or "",
            details=details or {},
        )

        # 2. Call repository with the expected signature
        await self.repo.log_event(
            payload=payload,
            actor_user_id=actor_user_id,
            ip_address=ip_address
        )

    async def query(self, tenant_id: UUID, q: AuditQuery) -> list[AuditLogResponse]:
        return await self.repo.query_events(tenant_id, q)