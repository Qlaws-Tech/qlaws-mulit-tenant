# app/modules/groups/repository.py

from typing import List
from uuid import UUID

from asyncpg import Connection

from app.modules.groups.schemas import GroupCreate, GroupResponse


class GroupRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    async def create(self, payload: GroupCreate) -> GroupResponse:
        row = await self.conn.fetchrow(
            """
            INSERT INTO groups (tenant_id, name, description)
            VALUES (
                current_setting('app.current_tenant_id', true)::uuid,
                $1,
                $2
            )
            RETURNING group_id, tenant_id, name, description, created_at
            """,
            payload.name,
            payload.description,
        )
        # member_count initially 0
        return GroupResponse(
            group_id=row["group_id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            member_count=0,
        )

    # ---------------------------------------------------------
    # MEMBERS
    # ---------------------------------------------------------
    async def add_member(self, group_id: UUID, user_id: UUID, tenant_id: UUID) -> bool:
        """
        Adds a member by linking to user_tenants for current tenant.
        """
        # Resolve user_tenant_id in current tenant
        print(f"{tenant_id}")
        ut_row = await self.conn.fetchrow(
            """
            SELECT user_tenant_id
            FROM user_tenants
            WHERE user_id = $1
              AND tenant_id = $2
            """,
            user_id,
            tenant_id,
        )
        if not ut_row:
            return False

        await self.conn.execute(
            """
            INSERT INTO group_members (group_id, user_tenant_id, tenant_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            group_id,
            ut_row["user_tenant_id"],
            tenant_id,
        )
        return True

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------
    async def list_groups(self) -> List[GroupResponse]:
        rows = await self.conn.fetch(
            """
            SELECT
                g.group_id,
                g.name,
                g.description,
                g.created_at,
                COUNT(DISTINCT gm.user_tenant_id) AS member_count
            FROM groups g
            LEFT JOIN group_members gm ON gm.group_id = g.group_id
            GROUP BY g.group_id, g.name, g.description, g.created_at
            ORDER BY g.created_at DESC
            """
        )
        return [GroupResponse(**r) for r in rows]
