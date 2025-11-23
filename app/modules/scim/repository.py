from asyncpg import Connection
from app.modules.scim.schemas import ScimUserCreate
from uuid import UUID


class ScimRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def upsert_user(self, data: ScimUserCreate, tenant_id: UUID):
        """
        Idempotent create/update logic for SCIM.
        """
        email = next((e.value for e in data.emails if e.primary), data.emails[0].value)

        # 1. Upsert Global User
        user_query = """
            INSERT INTO users (primary_email, display_name, hashed_password)
            VALUES ($1, $2, 'scim_managed') -- Placeholder pwd for SSO users
            ON CONFLICT (lower(primary_email)) 
            DO UPDATE SET 
                display_name = EXCLUDED.display_name,
                updated_at = now()
            RETURNING user_id
        """
        display_name = f"{data.name.givenName} {data.name.familyName}"
        user_id = await self.conn.fetchval(user_query, email, display_name)

        # 2. Link to Tenant (Upsert UserTenant)
        # We map SCIM 'active' status to our internal status
        status = 'active' if data.active else 'suspended'

        link_query = """
            INSERT INTO user_tenants (
                tenant_id, user_id, tenant_email, status, tenant_role
            )
            VALUES ($1, $2, $3, $4, 'member')
            ON CONFLICT (tenant_id, user_id)
            DO UPDATE SET 
                status = EXCLUDED.status,
                updated_at = now()
            RETURNING user_tenant_id, status
        """
        await self.conn.execute(link_query, tenant_id, user_id, email, status)

        return user_id

    async def get_user_by_id(self, user_id: UUID, tenant_id: UUID):
        """Fetches user ensuring they belong to the calling tenant."""
        query = """
            SELECT u.user_id, u.primary_email, u.display_name, ut.status
            FROM users u
            JOIN user_tenants ut ON u.user_id = ut.user_id
            WHERE u.user_id = $1 AND ut.tenant_id = $2
        """
        return await self.conn.fetchrow(query, user_id, tenant_id)

    async def delete_user(self, user_id: UUID, tenant_id: UUID):
        """SCIM Delete usually means 'Deactivate' or 'Unlink'."""
        query = """
            UPDATE user_tenants SET status = 'suspended', updated_at = now()
            WHERE user_id = $1 AND tenant_id = $2
        """
        await self.conn.execute(query, user_id, tenant_id)