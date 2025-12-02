# app/modules/scim/router.py

from fastapi import APIRouter, Depends, Header, Request, status
from app.dependencies.database import get_db_connection
from app.modules.scim.schemas import SCIMUserCreate, SCIMUserResponse
from app.modules.scim.service import SCIMService

router = APIRouter(
    prefix="/scim/v2",
    tags=["SCIM"],
)


def get_scim_service(conn=Depends(get_db_connection)) -> SCIMService:
    """
    Note:
    - In tests, get_db_connection is overridden to yield a connection with
      app.current_tenant_id already set via set_config().
    - In production, you might want a dedicated SCIM dependency that sets
      app.current_tenant_id from the API key’s tenant_id.
    """
    return SCIMService(conn)


@router.post(
    "/Users",
    response_model=SCIMUserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def scim_create_user(
    payload: SCIMUserCreate,
    request: Request,
    authorization: str = Header(None, alias="Authorization"),
    service: SCIMService = Depends(get_scim_service),
):
    """
    SCIM User creation endpoint.

    Okta / Azure sends:
    - Authorization: Bearer <API_KEY>
    - SCIM JSON body

    We provision into the tenant tied to the API key.
    """
    return await service.create_scim_user(request, payload, authorization)
