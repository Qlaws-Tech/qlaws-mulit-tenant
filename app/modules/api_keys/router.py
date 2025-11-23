from fastapi import APIRouter, Depends, status
from uuid import UUID
from typing import List
from app.dependencies.rls import get_tenant_db_connection
from app.modules.api_keys.repository import ApiKeyRepository
from app.modules.api_keys.service import ApiKeyService
from app.modules.api_keys.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse

router = APIRouter()

async def get_apikey_service(conn = Depends(get_tenant_db_connection)):
    return ApiKeyService(ApiKeyRepository(conn))

@router.post("/", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    service: ApiKeyService = Depends(get_apikey_service)
):
    """Create a new API Key. Returns the secret key ONLY once."""
    return await service.create_api_key(data)

@router.get("/", response_model=List[ApiKeyResponse])
async def list_api_keys(service: ApiKeyService = Depends(get_apikey_service)):
    return await service.list_keys()

@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    service: ApiKeyService = Depends(get_apikey_service)
):
    await service.revoke_key(key_id)