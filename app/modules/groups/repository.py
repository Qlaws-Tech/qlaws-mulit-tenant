from asyncpg import Connection
from typing import List, Optional, Dict
from uuid import UUID
from app.modules.groups.schemas import GroupCreate, GroupUpdate, GroupResponse


class GroupRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create(self, group: GroupCreate) -> GroupResponse:
        # Explicitly insert tenant_id from session for RLS compatibility
        query = """
            INSERT INTO groups (name, description, tenant_id)
            VALUES ($1, $2, current_setting('app.current_tenant_id')::uuid)
            RETURNING group_id, name, description, created_at
        """
        row = await self.conn.fetchrow(query, group.name, group.description)
        return GroupResponse(**dict(row), member_count=0, roles=[])

    async def list_groups(self) -> List[GroupResponse]:
        # Complex query to aggregate roles and count members
        query = """
            SELECT g.group_id, g.name, g.description, g.created_at,
                   (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.group_id) as member_count,
                   array_remove(array_agg(r.name), NULL) as roles
            FROM groups g
            LEFT JOIN group_roles gr ON g.group_id = gr.group_id
            LEFT JOIN roles r ON gr.role_id = r.role_id
            GROUP BY g.group_id
        """
        rows = await self.conn.fetch(query)
        return [GroupResponse(**dict(row)) for row in rows]

    async def add_member(self, group_id: UUID, user_id: UUID):
        # 1. Resolve user_id -> user_tenant_id for the CURRENT tenant
        #    We use the session variable to ensure we only find the user in this tenant
        lookup_query = """
            SELECT user_tenant_id FROM user_tenants 
            WHERE user_id = $1 
            AND tenant_id = current_setting('app.current_tenant_id')::uuid
        """
        ut_id = await self.conn.fetchval(lookup_query, user_id)

        if not ut_id:
            return False  # User is not part of this tenant

        # 2. Insert into group_members
        try:
            await self.conn.execute("""
                INSERT INTO group_members (group_id, user_tenant_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, group_id, ut_id)
            return True
        except Exception:
            return False

    async def assign_role(self, group_id: UUID, role_id: UUID):
        # RLS on 'group_roles' checks if group belongs to tenant
        # We also verify role belongs to tenant via the foreign key RLS logic
        try:
            await self.conn.execute("""
                INSERT INTO group_roles (group_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, group_id, role_id)
            return True
        except Exception:
            return False