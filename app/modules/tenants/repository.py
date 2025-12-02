# app/modules/tenants/repository.py

from typing import Optional, List
from uuid import UUID
from asyncpg import Connection

from app.modules.tenants.schemas import TenantCreate, TenantResponse


class TenantRepository:
    """
    Low-level data access for tenants.
    Relies on RLS at the database level for isolation when tenant_id is set.
    """

    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(self, payload: TenantCreate) -> TenantResponse:
        """
        Inserts a new tenant row. Domain is stored in lowercase.
        Status defaults to 'active'.
        """
        row = await self.conn.fetchrow(
            """
            INSERT INTO tenants (name, domain, plan, region, status)
            VALUES ($1, lower($2), $3, COALESCE($4, 'us-east-1'), 'active')
            RETURNING tenant_id, name, domain, plan, region, status, created_at
            """,
            payload.name,
            payload.domain,
            payload.plan,
            payload.region,
        )

        return TenantResponse(**row)

    async def get_by_id(self, tenant_id: UUID) -> Optional[TenantResponse]:
        row = await self.conn.fetchrow(
            """
            SELECT tenant_id, name, domain, plan, region, status, created_at
            FROM tenants
            WHERE tenant_id = $1
            """,
            tenant_id,
        )
        return TenantResponse(**row) if row else None

    async def get_by_domain(self, domain: str) -> Optional[TenantResponse]:
        row = await self.conn.fetchrow(
            """
            SELECT tenant_id, name, domain, plan, region, status, created_at
            FROM tenants
            WHERE domain = lower($1)
            """,
            domain,
        )
        return TenantResponse(**row) if row else None

    async def list_tenants(self) -> List[TenantResponse]:
        rows = await self.conn.fetch(
            """
            SELECT tenant_id, name, domain, plan, region, status, created_at
            FROM tenants
            ORDER BY created_at DESC
            """
        )
        return [TenantResponse(**r) for r in rows]
