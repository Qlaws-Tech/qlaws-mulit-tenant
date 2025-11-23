from asyncpg import Connection
from typing import List, Optional
from datetime import datetime
from uuid import UUID, uuid4
import json
from app.modules.audit.schemas import AuditLogCreate


class AuditRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def log_event(self, log: AuditLogCreate):
        """
        Inserts an immutable audit record.
        """
        try:
            tenant_id = await self.conn.fetchval("SHOW app.current_tenant_id")
        except:
            tenant_id = None

        # Generate UUID here
        new_audit_id = uuid4()

        query = """
            INSERT INTO audit_logs (
                audit_id, tenant_id, actor_user_id, action_type, 
                resource_type, resource_id, details, ip_address
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """

        await self.conn.execute(
            query,
            new_audit_id,  # $1
            tenant_id,  # $2
            log.actor_user_id,  # $3 <--- Ensure this maps to schema field
            log.action_type,  # $4
            log.resource_type,  # $5
            log.resource_id,  # $6
            json.dumps(log.details),  # $7
            log.ip_address  # $8 <--- Ensure this maps to schema field
        )

    async def get_logs(
            self,
            user_id: Optional[str] = None,
            action: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            limit: int = 50,
            offset: int = 0
    ) -> List[dict]:
        """
        Fetches audit logs.
        Note: We MUST select actor_user_id and ip_address for them to appear in the API response.
        """
        query = """
            SELECT event_time, actor_user_id, action_type, resource_type, resource_id, details, ip_address
            FROM audit_logs
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if user_id:
            query += f" AND actor_user_id = ${param_idx}::uuid"
            params.append(user_id)
            param_idx += 1

        if action:
            query += f" AND action_type = ${param_idx}"
            params.append(action)
            param_idx += 1

        if start_date:
            query += f" AND event_time >= ${param_idx}"
            params.append(start_date)
            param_idx += 1

        if end_date:
            query += f" AND event_time <= ${param_idx}"
            params.append(end_date)
            param_idx += 1

        query += f" ORDER BY event_time DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.append(limit)
        params.append(offset)

        rows = await self.conn.fetch(query, *params)
        return [dict(row) for row in rows]