from typing import List, Optional
from datetime import datetime
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogResponse


class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def get_tenant_logs(
            self,
            user_id: Optional[str],
            action: Optional[str],
            start_date: Optional[datetime],
            end_date: Optional[datetime],
            limit: int,
            offset: int
    ) -> List[AuditLogResponse]:

        raw_logs = await self.repo.get_logs(user_id, action, start_date, end_date, limit, offset)

        # Convert raw dictionary rows to Pydantic models (handles JSON parsing automatically)
        parsed_logs = []
        for row in raw_logs:
            # Ensure details is a dict if driver returns string
            if isinstance(row.get('details'), str):
                import json
                row['details'] = json.loads(row['details'])
            parsed_logs.append(AuditLogResponse(**row))

        return parsed_logs