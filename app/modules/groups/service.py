# app/modules/groups/service.py

from typing import List
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.groups.repository import GroupRepository
from app.modules.groups.schemas import GroupCreate, GroupResponse
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate


class GroupService:
    def __init__(self, conn):
        self.conn = conn
        self.repo = GroupRepository(conn)
        self.audit_repo = AuditRepository(conn)

    async def create_group(self, payload: GroupCreate) -> GroupResponse:
        grp = await self.repo.create(payload)
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="group.create",
                resource_type="group",
                resource_id=str(grp.group_id),
                details={"name": grp.name},
            )
        )
        return grp

    async def add_member(self, group_id: UUID, user_id: UUID, tenant_id: UUID) -> GroupResponse:
        print(f"{tenant_id}")
        success = await self.repo.add_member(group_id, user_id, tenant_id)

        if not success:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "User not part of current tenant",
            )

        groups = await self.repo.list_groups()
        for g in groups:
            if g.group_id == group_id:
                await self.audit_repo.log_event(
                    AuditLogCreate(
                        action_type="group.add_member",
                        resource_type="group",
                        resource_id=str(group_id),
                        details={"user_id": str(user_id)},
                    )
                )
                return g

        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")

    async def list_groups(self) -> List[GroupResponse]:
        return await self.repo.list_groups()
