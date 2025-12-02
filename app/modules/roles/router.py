# app/modules/roles/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.permissions import require_permissions
from app.modules.roles.schemas import RoleCreate, RoleUpdate, RoleResponse
from app.modules.roles.service import RoleService

router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
)


def get_role_service(conn=Depends(get_tenant_db_connection)) -> RoleService:
    return RoleService(conn)


@router.get(
    "/",
    response_model=List[RoleResponse],
    dependencies=[Depends(require_permissions(["role.read"]))],
)
async def list_roles(service: RoleService = Depends(get_role_service)):
    return await service.list_roles()


@router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(["role.create"]))],
)
async def create_role(
    body: RoleCreate,
    service: RoleService = Depends(get_role_service),
):
    return await service.create_role(body)


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(require_permissions(["role.update"]))],
)
async def update_role(
    role_id: UUID,
    body: RoleUpdate,
    service: RoleService = Depends(get_role_service),
):
    return await service.update_role(role_id, body)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(["role.update"]))],
)
async def delete_role(
    role_id: UUID,
    service: RoleService = Depends(get_role_service),
):
    await service.delete_role(role_id)
    return None
