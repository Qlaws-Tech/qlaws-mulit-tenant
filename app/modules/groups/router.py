# app/modules/groups/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Body

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.permissions import require_permission
from app.dependencies.auth_utils import get_current_user_id
from fastapi import Request

from app.modules.groups.schemas import (
    GroupCreate,
    GroupUpdate,
    GroupRolesUpdate,
    GroupResponse,
)
from app.modules.groups.service import GroupService


router = APIRouter(
    prefix="/groups",
    tags=["Groups"],
)


def get_group_service(conn=Depends(get_tenant_db_connection)) -> GroupService:
    return GroupService(conn)


@router.post(
    "/",
    response_model=GroupResponse,
    dependencies=[Depends(require_permission("group.manage"))],
)
async def create_group(
    body: GroupCreate,
    service: GroupService = Depends(get_group_service),
    current_user_id: UUID = Depends(get_current_user_id),  # kept for audit compatibility
):
    # current_user_id is available if you want to log who created the group
    return await service.create_group(body)


@router.get(
    "/",
    response_model=List[GroupResponse],
    dependencies=[Depends(require_permission("group.read"))],
)
async def list_groups(
    service: GroupService = Depends(get_group_service),
):
    return await service.list_groups()


@router.post(
    "/{group_id}/members",
    response_model=GroupResponse,
    dependencies=[Depends(require_permission("group.manage"))],
)
async def add_member_to_group(
    request: Request,
    group_id: UUID,
    payload: dict = Body(..., example={"user_id": "aaaaaaaa-bbbb-cccc-dddd-111111111111"}),
    service: GroupService = Depends(get_group_service),
    current_user_id: UUID = Depends(get_current_user_id),
):
    """
    Adds a member to the group using user_id from the body.
    """
    user_id_str = payload.get("user_id")
    if not user_id_str:
        from fastapi import HTTPException, status
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Missing 'user_id' in request body",
        )

    user_id = UUID(user_id_str)
    tenant_id = getattr(request.state, "tenant_id", None)
    print(f"Tenant ID :  {tenant_id}")
    return await service.add_member(group_id, user_id, tenant_id)
