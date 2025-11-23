from fastapi import HTTPException
from uuid import UUID
from typing import List
from app.modules.groups.repository import GroupRepository
from app.modules.groups.schemas import GroupCreate, GroupResponse

class GroupService:
    def __init__(self, repo: GroupRepository):
        self.repo = repo

    async def create_group(self, data: GroupCreate) -> GroupResponse:
        return await self.repo.create(data)

    async def list_groups(self) -> List[GroupResponse]:
        return await self.repo.list_groups()

    async def add_user_to_group(self, group_id: UUID, user_id: UUID):
        success = await self.repo.add_member(group_id, user_id)
        if not success:
            raise HTTPException(404, "User not found in this tenant or Group does not exist")
        return {"message": "Member added"}

    async def add_role_to_group(self, group_id: UUID, role_id: UUID):
        success = await self.repo.assign_role(group_id, role_id)
        if not success:
            raise HTTPException(400, "Could not assign role (check if Role exists)")
        return {"message": "Role assigned"}