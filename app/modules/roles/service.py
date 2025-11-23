from fastapi import HTTPException
from uuid import UUID
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreate, RoleUpdate

class RoleService:
    def __init__(self, repo: RoleRepository):
        self.repo = repo

    async def create(self, data: RoleCreate):
        # Future logic: Validate permission keys exist in 'permissions' table?
        return await self.repo.create_role(data)

    async def list_all(self):
        return await self.repo.get_roles()

    async def update(self, role_id: UUID, data: RoleUpdate):
        role = await self.repo.update_role(role_id, data)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        return role

    async def delete(self, role_id: UUID):
        deleted = await self.repo.delete_role(role_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Role not found or is builtin")