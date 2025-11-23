from fastapi import APIRouter, Depends, status
from typing import List
from uuid import UUID
from app.dependencies.rls import get_tenant_db_connection
from app.modules.groups.repository import GroupRepository
from app.modules.groups.service import GroupService
from app.modules.groups.schemas import GroupCreate, GroupResponse, AddMemberRequest, AssignRoleRequest

router = APIRouter()

async def get_group_service(conn = Depends(get_tenant_db_connection)):
    return GroupService(GroupRepository(conn))

@router.post("/", response_model=GroupResponse, status_code=201)
async def create_group(data: GroupCreate, service: GroupService = Depends(get_group_service)):
    return await service.create_group(data)

@router.get("/", response_model=List[GroupResponse])
async def list_groups(service: GroupService = Depends(get_group_service)):
    return await service.list_groups()

@router.post("/{group_id}/members", status_code=200)
async def add_member(
    group_id: UUID,
    payload: AddMemberRequest,
    service: GroupService = Depends(get_group_service)
):
    return await service.add_user_to_group(group_id, payload.user_id)

@router.post("/{group_id}/roles", status_code=200)
async def assign_role(
    group_id: UUID,
    payload: AssignRoleRequest,
    service: GroupService = Depends(get_group_service)
):
    return await service.add_role_to_group(group_id, payload.role_id)