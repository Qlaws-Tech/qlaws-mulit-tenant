# app/modules/sso/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.permissions import require_permissions
from app.modules.sso.schemas import (
    SSOProviderCreate,
    SSOProviderUpdate,
    SSOProviderResponse,
)
from app.modules.sso.service import SSOService

router = APIRouter(
    prefix="/sso",
    tags=["SSO"],
)


def get_sso_service(conn=Depends(get_tenant_db_connection)) -> SSOService:
    return SSOService(conn)


@router.post(
    "/",
    response_model=SSOProviderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(["sso.manage"]))],
)
async def create_sso_provider(
    body: SSOProviderCreate,
    service: SSOService = Depends(get_sso_service),
):
    return await service.create_provider(body)


@router.get(
    "/",
    response_model=List[SSOProviderResponse],
    dependencies=[Depends(require_permissions(["sso.read"]))],
)
async def list_sso_providers(
    service: SSOService = Depends(get_sso_service),
):
    return await service.list_providers()


@router.patch(
    "/{provider_id}",
    response_model=SSOProviderResponse,
    dependencies=[Depends(require_permissions(["sso.manage"]))],
)
async def update_sso_provider(
    provider_id: UUID,
    body: SSOProviderUpdate,
    service: SSOService = Depends(get_sso_service),
):
    return await service.update_provider(provider_id, body)


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(["sso.manage"]))],
)
async def delete_sso_provider(
    provider_id: UUID,
    service: SSOService = Depends(get_sso_service),
):
    await service.delete_provider(provider_id)
    return None
