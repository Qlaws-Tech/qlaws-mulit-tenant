from fastapi import APIRouter, Depends, Request, status
from app.dependencies.database import get_db_connection
from app.modules.scim.service import ScimService
from app.modules.scim.repository import ScimRepository
from app.modules.api_keys.repository import ApiKeyRepository
from app.modules.scim.schemas import ScimUserCreate, ScimResponse

router = APIRouter()


async def get_scim_service(conn=Depends(get_db_connection)):
    # We use raw connection because SCIM auth is handled manually via API Keys
    # inside the service, not via the standard RLS dependency.
    return ScimService(
        ScimRepository(conn),
        ApiKeyRepository(conn)
    )


@router.post("/Users", response_model=ScimResponse, status_code=201)
async def scim_create_user(
        payload: ScimUserCreate,
        request: Request,
        service: ScimService = Depends(get_scim_service)
):
    # Extract Bearer token manually
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")

    return await service.create_user(token, payload)

# TODO: Add GET /Users/{id} and PATCH /Users/{id} following similar pattern