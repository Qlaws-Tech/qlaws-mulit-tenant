# app/modules/audit/repository.py

import json
from typing import List, Optional, Any
from uuid import UUID

from asyncpg import Connection

from app.modules.audit.schemas import AuditLogCreate, AuditLogEntry, AuditQuery, AuditLogResponse


class AuditRepository:
    """
    Thin wrapper around audit_logs table.
    Uses current_setting('app.current_tenant_id') for tenant scoping.
    """

    def __init__(self, conn: Connection):
        self.conn = conn

    async def log_event(
            self,
            payload: AuditLogCreate,
            actor_user_id: Optional[UUID] = None,
            ip_address: Optional[str] = None,
    ) -> None:
        """
        Insert an audit log entry.
        """
        details_json = json.dumps(payload.details or {})

        await self.conn.execute(
            """
            INSERT INTO audit_logs (
                audit_id,
                tenant_id,
                actor_user_id,
                action_type,
                resource_type,
                resource_id,
                ip_address,
                details
            )
            VALUES (
                uuid_generate_v4(),
                current_setting('app.current_tenant_id', true)::uuid,
                $1,
                $2,
                $3,
                $4,
                $5,
                $6::jsonb
            )
            """,
            actor_user_id,
            payload.action_type,
            payload.resource_type,
            payload.resource_id,
            ip_address,
            details_json,
        )

    async def list_logs(self, limit: int = 100, offset: int = 0) -> List[AuditLogEntry]:
        """
        Basic list (deprecated in favor of query_events, but kept for compatibility).
        """
        rows = await self.conn.fetch(
            """
            SELECT
                audit_id,
                tenant_id,
                actor_user_id,
                action_type,
                resource_type,
                resource_id,
                ip_address,
                details,
                created_at
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [AuditLogEntry(**r) for r in rows]

    async def query_events(self, tenant_id: UUID, q: AuditQuery) -> List[AuditLogResponse]:
        """
        Dynamic filtering for audit logs.
        """
        # 1. Base Query
        sql = """
            SELECT
                audit_id,
                tenant_id,
                actor_user_id,
                action_type,
                resource_type,
                resource_id,
                ip_address,
                details,
                created_at
            FROM audit_logs
            WHERE tenant_id = $1
        """
        params: List[Any] = [tenant_id]

        # 2. Dynamic Filters
        # Note: We start params at $1, so next is $2
        idx = 2

        if q.action_type:
            sql += f" AND action_type = ${idx}"
            params.append(q.action_type)
            idx += 1

        if q.resource_type:
            sql += f" AND resource_type = ${idx}"
            params.append(q.resource_type)
            idx += 1

        if q.actor_user_id:
            sql += f" AND actor_user_id = ${idx}"
            params.append(q.actor_user_id)
            idx += 1

        if q.start_date:
            sql += f" AND created_at >= ${idx}"
            params.append(q.start_date)
            idx += 1

        if q.end_date:
            sql += f" AND created_at <= ${idx}"
            params.append(q.end_date)
            idx += 1

        # 3. Sorting and Pagination
        sql += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.append(q.limit)
        params.append(q.offset)

        rows = await self.conn.fetch(sql, *params)
        return [AuditLogResponse(**r) for r in rows]