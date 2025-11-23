from fastapi import APIRouter, Depends, status
from typing import List
from uuid import UUID
from app.dependencies.rls import get_tenant_db_connection
from app.modules.roles.repository import RoleRepository
from app.modules.roles.service import RoleService
from app.modules.roles.schemas import RoleCreate, RoleUpdate, RoleResponse

router = APIRouter()

async def get_role_service(conn = Depends(get_tenant_db_connection)):
    return RoleService(RoleRepository(conn))

@router.post("/", response_model=RoleResponse, status_code=201)
async def create_role(data: RoleCreate, service: RoleService = Depends(get_role_service)):
    return await service.create(data)

@router.get("/", response_model=List[RoleResponse])
async def list_roles(service: RoleService = Depends(get_role_service)):
    return await service.list_all()

@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(role_id: UUID, data: RoleUpdate, service: RoleService = Depends(get_role_service)):
    return await service.update(role_id, data)

@router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: UUID, service: RoleService = Depends(get_role_service)):
    await service.delete(role_id)