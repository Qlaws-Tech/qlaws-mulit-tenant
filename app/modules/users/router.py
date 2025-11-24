from fastapi import APIRouter, Depends, status, Request, BackgroundTasks, HTTPException
from typing import List, Optional
from uuid import UUID
from jose import jwt, JWTError
from app.core.config import settings
from app.dependencies.rls import get_tenant_db_connection
from app.dependencies.permissions import require_permission
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.modules.users.schemas import UserCreate, UserResponse, UserUpdate, UserContextResponse
from app.modules.audit.repository import AuditRepository
from app.dependencies.auth_utils import get_current_user_id

router = APIRouter()


async def get_user_service(conn=Depends(get_tenant_db_connection)) -> UserService:
    user_repo = UserRepository(conn)
    audit_repo = AuditRepository(conn)
    return UserService(user_repo, audit_repo)


# Helper to get current user ID from token for Audit Logging



# --- Bootstrap Endpoint (/me) ---
@router.get("/me", response_model=UserContextResponse)
async def get_current_user_context(
        request: Request,
        conn=Depends(get_tenant_db_connection)
):
    """
    Bootstrap endpoint. Returns User Profile + Permissions + Redirect URL.
    This endpoint is open to any logged-in user (no specific permission required).
    """
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    user_id = payload.get("sub")
    tenant_id = payload.get("tid")

    # Re-instantiate service manually since we extracted IDs from token directly
    user_repo = UserRepository(conn)
    audit_repo = AuditRepository(conn)
    service = UserService(user_repo, audit_repo)

    return await service.get_me(user_id, tenant_id)


# --- Secure CRUD Operations ---

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("user.create"))]  # <--- Security Guard
)
async def create_user(
        request: Request,  # <--- Need request for IP/Token
        user_data: UserCreate,
        background_tasks: BackgroundTasks,
        service: UserService = Depends(get_user_service)
):
    """
    Create a new user. Records Audit Log with Actor ID and IP.
    """
    actor_id = get_current_user_id(request)
    client_ip = request.client.host

    return await service.on_board_user(
        user_data,
        background_tasks=background_tasks,
        current_user_id=actor_id,
        ip_address=client_ip
    )


@router.get("/", response_model=List[UserResponse])
async def list_users(
        service: UserService = Depends(get_user_service)
):
    """
    List all users belonging to the current tenant.
    Usually open to all tenant members.
    """
    return await service.get_tenant_users()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
        user_id: UUID,
        service: UserService = Depends(get_user_service)
):
    """Get specific user details."""
    return await service.get_by_id(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("user.update"))]  # <--- Security Guard
)
async def update_user(
        request: Request,
        user_id: UUID,
        data: UserUpdate,
        service: UserService = Depends(get_user_service)
):
    """
    Update user status or role.
    """
    actor_id = get_current_user_id(request)
    client_ip = request.client.host

    return await service.update_user(
        user_id,
        data,
        current_user_id=actor_id,
        ip_address=client_ip
    )


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[Depends(require_permission("user.delete"))]  # <--- Security Guard
)
async def remove_user(
        request: Request,
        user_id: UUID,
        service: UserService = Depends(get_user_service)
):
    """
    Remove a user from the tenant.
    """
    actor_id = get_current_user_id(request)
    client_ip = request.client.host

    await service.remove_user(
        user_id,
        current_user_id=actor_id,
        ip_address=client_ip
    )