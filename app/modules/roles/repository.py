# app/modules/roles/repository.py

from typing import List, Optional
from uuid import UUID

import asyncpg
from asyncpg import Connection

from app.modules.roles.schemas import RoleCreate, RoleUpdate, RoleResponse


class RoleRepository:
    """
    Tenant-scoped Role repository.

    Relies on:
        - RLS using current_setting('app.current_tenant_id')
        - Enterprise schema: roles, role_permissions, permissions, tenants
    """

    def __init__(self, conn: Connection):
        self.conn = conn

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    async def create_role(self, payload: RoleCreate) -> RoleResponse:
        """
        Inserts a new role for current tenant and links permissions.
        """
        async with self.conn.transaction():
            row = await self.conn.fetchrow(
                """
                INSERT INTO roles (tenant_id, name, description)
                VALUES (
                    current_setting('app.current_tenant_id', true)::uuid,
                    $1,
                    $2
                )
                RETURNING role_id, name, description, created_at
                """,
                payload.name,
                payload.description,
            )

            if payload.permission_keys:
                await self._set_role_permissions(
                    row["role_id"],
                    payload.permission_keys,
                )

        return await self.get_role(row["role_id"])

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------
    async def get_role(self, role_id: UUID) -> Optional[RoleResponse]:
        row = await self.conn.fetchrow(
            """
            SELECT
                r.role_id,
                r.name,
                r.description,
                r.created_at,
                COALESCE(
                    ARRAY_AGG(DISTINCT p.key) FILTER (WHERE p.key IS NOT NULL),
                    '{}'
                ) AS permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON rp.role_id = r.role_id
            LEFT JOIN permissions p ON p.permission_id = rp.permission_id
            WHERE r.role_id = $1
            GROUP BY r.role_id, r.name, r.description, r.created_at
            """,
            role_id,
        )
        return RoleResponse(**row) if row else None

    async def get_role_by_name(self, name: str, tenant_id: UUID) -> Optional[RoleResponse]:
        """Get a role by name within a tenant."""
        row = await self.conn.fetchrow(
            """
            SELECT
                r.role_id,
                r.name,
                r.description,
                r.created_at,
                COALESCE(
                    ARRAY_AGG(DISTINCT p.key) FILTER (WHERE p.key IS NOT NULL),
                    '{}'
                ) AS permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON rp.role_id = r.role_id
            LEFT JOIN permissions p ON p.permission_id = rp.permission_id
            WHERE r.name = $1 AND r.tenant_id = $2
            GROUP BY r.role_id, r.name, r.description, r.created_at
            """,
            name,
            tenant_id,
        )
        return RoleResponse(**row) if row else None

    async def get_roles(self) -> List[RoleResponse]:
        rows = await self.conn.fetch(
            """
            SELECT
                r.role_id,
                r.name,
                r.description,
                r.created_at,
                COALESCE(
                    ARRAY_AGG(DISTINCT p.key) FILTER (WHERE p.key IS NOT NULL),
                    '{}'
                ) AS permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON rp.role_id = r.role_id
            LEFT JOIN permissions p ON p.permission_id = rp.permission_id
            GROUP BY r.role_id, r.name, r.description, r.created_at
            ORDER BY r.created_at DESC
            """
        )
        return [RoleResponse(**r) for r in rows]

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------
    async def update_role(self, role_id: UUID, payload: RoleUpdate) -> RoleResponse:
        async with self.conn.transaction():
            if payload.name is not None:
                await self.conn.execute(
                    """
                    UPDATE roles
                    SET name = $2
                    WHERE role_id = $1
                    """,
                    role_id,
                    payload.name,
                )

            if payload.description is not None:
                await self.conn.execute(
                    """
                    UPDATE roles
                    SET description = $2
                    WHERE role_id = $1
                    """,
                    role_id,
                    payload.description,
                )

            if payload.permission_keys is not None:
                await self._set_role_permissions(role_id, payload.permission_keys)

        updated = await self.get_role(role_id)
        return updated

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------
    async def delete_role(self, role_id: UUID):
        await self.conn.execute(
            "DELETE FROM roles WHERE role_id = $1",
            role_id,
        )

    # ---------------------------------------------------------
    # USER ROLE ASSIGNMENT (NEW METHODS)
    # ---------------------------------------------------------
    async def assign_role(
            self,
            user_tenant_id: UUID,
            role_id: UUID,
    ) -> bool:
        """
        Assign a role to a user (via user_roles table).
        """
        try:
            await self.conn.execute(
                """
                INSERT INTO user_roles (user_tenant_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT (user_tenant_id, role_id) DO NOTHING
                """,
                user_tenant_id,
                role_id,
            )
            return True
        except Exception:
            return False

    async def assign_role_by_name(
            self,
            user_tenant_id: UUID,
            role_name: str,
            tenant_id: UUID,
    ) -> bool:
        """
        Assign a role to a user by role name.
        """
        # Get role_id from name
        role_row = await self.conn.fetchrow(
            "SELECT role_id FROM roles WHERE name = $1 AND tenant_id = $2",
            role_name,
            tenant_id,
        )

        if not role_row:
            return False

        return await self.assign_role(user_tenant_id, role_row["role_id"])

    async def remove_role(
            self,
            user_tenant_id: UUID,
            role_id: UUID,
    ) -> bool:
        """
        Remove a role from a user.
        """
        result = await self.conn.execute(
            """
            DELETE FROM user_roles
            WHERE user_tenant_id = $1 AND role_id = $2
            """,
            user_tenant_id,
            role_id,
        )
        return "DELETE 1" in result

    async def get_user_roles(
            self,
            user_tenant_id: UUID,
    ) -> List[RoleResponse]:
        """
        Get all roles assigned to a user.
        """
        rows = await self.conn.fetch(
            """
            SELECT
                r.role_id,
                r.name,
                r.description,
                r.created_at,
                COALESCE(
                    ARRAY_AGG(DISTINCT p.key) FILTER (WHERE p.key IS NOT NULL),
                    '{}'
                ) AS permissions
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.role_id
            LEFT JOIN role_permissions rp ON rp.role_id = r.role_id
            LEFT JOIN permissions p ON p.permission_id = rp.permission_id
            WHERE ur.user_tenant_id = $1
            GROUP BY r.role_id, r.name, r.description, r.created_at
            """,
            user_tenant_id,
        )
        return [RoleResponse(**r) for r in rows]

    async def assign_roles_to_user(
            self,
            user_tenant_id: UUID,
            role_names: List[str],
            tenant_id: UUID,
    ) -> int:
        """
        Assign multiple roles to a user by role names.
        Returns count of roles assigned.
        """
        assigned = 0
        for role_name in role_names:
            success = await self.assign_role_by_name(
                user_tenant_id=user_tenant_id,
                role_name=role_name,
                tenant_id=tenant_id,
            )
            if success:
                assigned += 1
        return assigned

    # ---------------------------------------------------------
    # PERMISSIONS HELPER
    # ---------------------------------------------------------
    async def _set_role_permissions(self, role_id: UUID, permission_keys: List[str]):
        # Clear existing
        await self.conn.execute(
            "DELETE FROM role_permissions WHERE role_id = $1",
            role_id,
        )

        # Handle wildcard: "*" = all permissions
        if permission_keys == ["*"]:
            all_perms = await self._fetch_permissions_for_keys(permission_keys)
            permission_keys = [p["key"] for p in all_perms]

        if not permission_keys:
            return

        # Ensure permissions exist
        rows = await self.conn.fetch(
            """
            SELECT permission_id, key
            FROM permissions
            WHERE key = ANY ($1::text[])
            """,
            permission_keys,
        )
        existing = {r["key"]: r["permission_id"] for r in rows}

        missing = [k for k in permission_keys if k not in existing]
        if missing:
            perms = await self.conn.fetch(
                """
                INSERT INTO permissions (key)
                SELECT unnest($1::text[])
                ON CONFLICT (key) DO UPDATE SET key = EXCLUDED.key
                RETURNING permission_id, key
                """,
                missing,
            )
            for r in perms:
                existing[r["key"]] = r["permission_id"]

        # Link to role
        tenant_id_row = await self.conn.fetchrow(
            "SELECT current_setting('app.current_tenant_id', true) AS tid"
        )
        tenant_id = tenant_id_row["tid"]

        inserts = [
            (role_id, existing[key], tenant_id)
            for key in permission_keys
        ]
        await self.conn.executemany(
            """
            INSERT INTO role_permissions (role_id, permission_id, tenant_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            inserts,
        )

    async def _fetch_permissions_for_keys(
            self, permission_keys: List[str]
    ) -> List[asyncpg.Record]:

        if not permission_keys:
            return []

        if "*" in permission_keys:
            return await self.conn.fetch(
                """
                SELECT permission_id, key
                FROM permissions
                ORDER BY key
                """
            )

        return await self.conn.fetch(
            """
            SELECT permission_id, key
            FROM permissions
            WHERE key = ANY($1::text[])
            ORDER BY key
            """,
            permission_keys,
        )