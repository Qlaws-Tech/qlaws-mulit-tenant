# app/modules/roles/service.py

from typing import List
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate, RoleUpdate, RoleResponse
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate


class RoleService:
    def __init__(self, conn):
        self.conn = conn
        self.repo = RoleRepository(conn)
        self.audit_repo = AuditRepository(conn)

    async def list_roles(self) -> List[RoleResponse]:
        return await self.repo.get_roles()

    async def create_role(self, payload: RoleCreate) -> RoleResponse:
        role = await self.repo.create_role(payload)
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="role.create",
                resource_type="role",
                resource_id=str(role.role_id),
                details={"name": role.name, "permissions": role.permissions},
            )
        )
        return role

    async def update_role(self, role_id: UUID, payload: RoleUpdate) -> RoleResponse:
        existing = await self.repo.get_role(role_id)
        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

        updated = await self.repo.update_role(role_id, payload)
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="role.update",
                resource_type="role",
                resource_id=str(role_id),
                details=payload.dict(exclude_unset=True),
            )
        )
        return updated

    async def delete_role(self, role_id: UUID):
        existing = await self.repo.get_role(role_id)
        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

        await self.repo.delete_role(role_id)
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="role.delete",
                resource_type="role",
                resource_id=str(role_id),
                details={"name": existing.name},
            )
        )
