from asyncpg import Connection
from typing import List, Optional
from uuid import UUID
from app.modules.roles.schemas import RoleCreate, RoleUpdate, RoleResponse

class RoleRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def create_role(self, role: RoleCreate) -> RoleResponse:
        # 1. Insert Role
        # FIX: We explicitly insert 'tenant_id' using the current session variable
        # casting it to ::uuid to match the column type.
        role_query = """
            INSERT INTO roles (name, description, is_builtin, tenant_id)
            VALUES ($1, $2, false, current_setting('app.current_tenant_id')::uuid)
            RETURNING role_id, name, description, is_builtin, created_at;
        """
        row = await self.conn.fetchrow(role_query, role.name, role.description)
        role_id = row['role_id']

        # 2. Assign Permissions (if any)
        perm_keys = []
        if role.permission_keys:
            # Bulk insert into role_permissions
            # The RLS on role_permissions checks if the parent 'role_id' belongs to the tenant.
            # Since we just successfully inserted the role above, this will pass.
            await self.conn.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT $1, p.permission_id
                FROM permissions p
                WHERE p.key = ANY($2::text[])
            """, role_id, role.permission_keys)
            perm_keys = role.permission_keys

        return RoleResponse(**dict(row), permissions=perm_keys)

    async def get_roles(self) -> List[RoleResponse]:
        # RLS filters this automatically!
        query = """
            SELECT r.role_id, r.name, r.description, r.is_builtin, r.created_at,
                   array_remove(array_agg(p.key), NULL) as permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON r.role_id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.permission_id
            GROUP BY r.role_id
        """
        rows = await self.conn.fetch(query)
        return [RoleResponse(**dict(row)) for row in rows]

    async def update_role(self, role_id: UUID, update: RoleUpdate) -> Optional[RoleResponse]:
        # 1. Update basic fields if provided
        if update.name or update.description:
            await self.conn.execute("""
                UPDATE roles 
                SET name = COALESCE($2, name),
                    description = COALESCE($3, description)
                WHERE role_id = $1
            """, role_id, update.name, update.description)

        # 2. Update Permissions (Full Replacement Strategy)
        if update.permission_keys is not None:
            # Remove old
            await self.conn.execute("DELETE FROM role_permissions WHERE role_id = $1", role_id)
            # Add new
            if update.permission_keys:
                await self.conn.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT $1, p.permission_id
                    FROM permissions p
                    WHERE p.key = ANY($2::text[])
                """, role_id, update.permission_keys)

        # 3. Fetch updated state
        return await self._get_single_role(role_id)

    async def delete_role(self, role_id: UUID) -> bool:
        # RLS prevents deleting other tenant's roles
        result = await self.conn.execute("DELETE FROM roles WHERE role_id = $1 AND is_builtin = false", role_id)
        return "DELETE 0" not in result

    async def _get_single_role(self, role_id: UUID) -> Optional[RoleResponse]:
        query = """
            SELECT r.role_id, r.name, r.description, r.is_builtin, r.created_at,
                   array_remove(array_agg(p.key), NULL) as permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON r.role_id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.permission_id
            WHERE r.role_id = $1
            GROUP BY r.role_id
        """
        row = await self.conn.fetchrow(query, role_id)
        return RoleResponse(**dict(row)) if row else None