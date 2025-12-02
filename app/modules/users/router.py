# app/modules/users/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.auth_utils import get_current_token_payload
from app.dependencies.permissions import require_permissions
from app.modules.users.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    CurrentUserResponse,
)
from app.modules.users.service import UserService

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


def get_user_service(conn=Depends(get_tenant_db_connection)) -> UserService:
    return UserService(conn)


# ---------------------------------------------------------
# LIST USERS
# ---------------------------------------------------------
@router.get(
    "/",
    response_model=List[UserResponse],
    dependencies=[Depends(require_permissions(["user.read"]))],
)
async def list_users(service: UserService = Depends(get_user_service)):
    return await service.list_users()


# ---------------------------------------------------------
# GET CURRENT USER PROFILE
# ---------------------------------------------------------
@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
async def get_me(
    payload=Depends(get_current_token_payload),
    service: UserService = Depends(get_user_service),
):
    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tid"])
    return await service.get_current_user_profile(user_id, tenant_id)


# ---------------------------------------------------------
# CREATE USER
# ---------------------------------------------------------
@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(["user.create"]))],
)
async def create_user(
    body: UserCreate,
    service: UserService = Depends(get_user_service),
):
    return await service.create_user(body)


# ---------------------------------------------------------
# UPDATE USER
# ---------------------------------------------------------
@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permissions(["user.update"]))],
)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    service: UserService = Depends(get_user_service),
):
    return await service.update_user(user_id, body)


# ---------------------------------------------------------
# DEACTIVATE USER
# ---------------------------------------------------------
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(["user.deactivate"]))],
)
async def deactivate_user(
    user_id: UUID,
    payload=Depends(get_current_token_payload),
    service: UserService = Depends(get_user_service),
):
    from uuid import UUID as _UUID
    tenant_id = _UUID(payload["tid"])
    await service.deactivate_user(user_id, tenant_id)
    return None
