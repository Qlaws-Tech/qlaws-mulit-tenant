from asyncpg import Connection
from typing import Optional
from uuid import UUID
from uuid import uuid4
import json
from app.modules.tenants.schemas import TenantCreate, TenantResponse


class TenantRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(self, tenant: TenantCreate) -> TenantResponse:
        # 1. Generate ID in Python first so we know it ahead of time
        new_id = uuid4()

        # 2. CRITICAL FIX: Set the RLS context *before* inserting.
        # The 'RETURNING' clause in the INSERT statement internally performs a SELECT.
        # If we don't set the context to match the new ID, the RLS SELECT policy
        # will hide the new row from us, causing a "row-level security policy violation" error.
        # 'true' as the 3rd arg makes this setting local to the transaction.
        await self.conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            str(new_id)
        )

        query = """
            INSERT INTO tenants (tenant_id, name, domain, plan, region, config, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'active')
            RETURNING tenant_id, name, status, created_at;
        """

        row = await self.conn.fetchrow(
            query,
            new_id,
            tenant.name,
            tenant.domain,
            tenant.plan,
            tenant.region,
            json.dumps(tenant.config)
        )
        return TenantResponse(**dict(row))

    async def get_by_domain(self, domain: str) -> Optional[UUID]:
        query = "SELECT tenant_id FROM tenants WHERE domain = $1"
        return await self.conn.fetchval(query, domain)