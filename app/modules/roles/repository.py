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
    # PERMISSIONS HELPER
    # ---------------------------------------------------------
    async def _set_role_permissions(self, role_id: UUID, permission_keys: list[str]):
        # Clear existing
        await self.conn.execute(
            "DELETE FROM role_permissions WHERE role_id = $1",
            role_id,
        )

        # Handle wildcard: "*" = all permissions
        if permission_keys == ["*"]:
            # Fetch all permissions (or subset, if ever extended)
            all_perms = await self._fetch_permissions_for_keys(permission_keys)
            # Normalize to list of keys (strings)
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
            # Auto-create missing permissions with null description
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
        """
        If permission_keys contains '*', return *all* permissions.
        Otherwise return only those whose key is in permission_keys.
        """
        if not permission_keys:
            return []

        # If wildcard present → all permissions
        if "*" in permission_keys:
            return await self.conn.fetch(
                """
                SELECT permission_id, key
                FROM permissions
                ORDER BY key
                """
            )

        # Otherwise fetch only requested ones
        return await self.conn.fetch(
            """
            SELECT permission_id, key
            FROM permissions
            WHERE key = ANY($1::text[])
            ORDER BY key
            """,
            permission_keys,
        )
