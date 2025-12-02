# app/modules/tenants/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.database import get_db_connection
from app.modules.tenants.schemas import (
    TenantCreate,
    TenantOnboardingResponse,
    TenantResponse,
)
from app.modules.tenants.repository import TenantRepository
from app.modules.users.repository import UserRepository
from app.modules.roles.repository import RoleRepository
from app.modules.tenants.service import TenantService

router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"],
)


def get_tenant_service(conn=Depends(get_db_connection)) -> TenantService:
    """
    Uses a system-level DB connection (no tenant RLS yet) for onboarding
    and tenant listing. Tests override get_db_connection to inject a
    rollback-enabled connection.
    """
    tenant_repo = TenantRepository(conn)
    user_repo = UserRepository(conn)
    role_repo = RoleRepository(conn)
    return TenantService(tenant_repo, user_repo, role_repo)


@router.post(
    "/",
    response_model=TenantOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    body: TenantCreate,
    service: TenantService = Depends(get_tenant_service),
):
    """
    Onboard a new tenant.

    - Returns 201 + TenantOnboardingResponse on success.
    - Raises 409 if domain already exists.
    - Raises 422 automatically for invalid plan (Pydantic enum).
    """
    return await service.onboard_tenant(body)


@router.get(
    "/",
    response_model=List[TenantResponse],
    status_code=status.HTTP_200_OK,
)
async def list_tenants(
    service: TenantService = Depends(get_tenant_service),
):
    """
    System-level list of tenants.
    """
    return await service.list_tenants()


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
)
async def get_tenant(
    tenant_id: UUID,
    service: TenantService = Depends(get_tenant_service),
):
    """
    Get a single tenant by ID.
    """
    return await service.get_tenant(tenant_id)
