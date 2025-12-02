# app/modules/api_keys/router.py

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies.database import get_tenant_db_connection
from app.dependencies.permissions import require_permissions
from app.modules.api_keys.schemas import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyWithPlain,
)
from app.modules.api_keys.repository import ApiKeyRepository
from app.modules.api_keys.service import ApiKeyService
from app.modules.audit.repository import AuditRepository

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"],
)


def get_api_key_service(conn=Depends(get_tenant_db_connection)) -> ApiKeyService:
    repo = ApiKeyRepository(conn)
    audit = AuditRepository(conn)
    return ApiKeyService(repo, audit)


@router.post(
    "/",
    response_model=ApiKeyWithPlain,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(["api_key.manage"]))],
)
async def create_api_key(
    body: ApiKeyCreate,
    service: ApiKeyService = Depends(get_api_key_service),
):
    return await service.create_api_key(body)


@router.get(
    "/",
    response_model=List[ApiKeyResponse],
    dependencies=[Depends(require_permissions(["api_key.manage"]))],
)
async def list_api_keys(
    service: ApiKeyService = Depends(get_api_key_service),
):
    return await service.list_keys()


@router.delete(
    "/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(["api_key.manage"]))],
)
async def delete_api_key(
    api_key_id: UUID,
    service: ApiKeyService = Depends(get_api_key_service),
):
    await service.delete_key(api_key_id)
    return None
