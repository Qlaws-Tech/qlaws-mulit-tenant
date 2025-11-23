from fastapi import APIRouter, Depends, Request
from typing import List
from app.dependencies.rls import get_tenant_db_connection
from app.dependencies.database import get_db_connection
from app.modules.sso.repository import SsoRepository
from app.modules.sso.service import SsoService
from app.modules.sso.schemas import SsoProviderCreate, SsoProviderResponse

router = APIRouter()


async def get_sso_service(conn=Depends(get_tenant_db_connection)):
    return SsoService(SsoRepository(conn))


# --- Configuration Endpoints (Protected) ---
@router.post("/", response_model=SsoProviderResponse, status_code=201)
async def configure_sso(
        data: SsoProviderCreate,
        service: SsoService = Depends(get_sso_service)
):
    return await service.create_provider(data)


@router.get("/", response_model=List[SsoProviderResponse])
async def list_sso_configs(service: SsoService = Depends(get_sso_service)):
    return await service.list_providers()


# --- Handshake Endpoints (Public) ---
@router.get("/login", status_code=307)
async def sso_login_redirect(
        tenant_id: str,
        alias: str,
        # We construct service manually or use raw conn for public endpoint if needed
        # Using get_sso_service would require Auth Token, which user doesn't have yet!
        conn=Depends(get_db_connection)
):
    """
    Redirects browser to the IdP.
    """
    # Instantiate service manually with raw connection (no RLS context yet)
    service = SsoService(SsoRepository(conn))
    result = await service.get_login_redirect(tenant_id, alias)
    return result


@router.get("/callback")
async def sso_callback(
        code: str,
        state: str,
        request: Request,
        conn=Depends(get_db_connection)
):
    """
    IdP redirects back here.
    """
    service = SsoService(SsoRepository(conn))
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    return await service.process_callback(conn, code, state, client_ip, user_agent)