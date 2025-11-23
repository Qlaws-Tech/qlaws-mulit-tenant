from fastapi import APIRouter, Depends, Request
from jose import jwt
from config_dev import settings
from app.dependencies.rls import get_tenant_db_connection
from app.modules.auth.mfa.service import MfaService
from app.modules.auth.mfa.repository import MfaRepository
from app.modules.auth.mfa.schemas import MfaSetupResponse, MfaVerifyRequest, MfaMethodResponse

router = APIRouter()


async def get_mfa_service(conn=Depends(get_tenant_db_connection)):
    return MfaService(MfaRepository(conn))


@router.get("/setup", response_model=MfaSetupResponse)
async def setup_mfa(request: Request, service: MfaService = Depends(get_mfa_service)):
    """
    Step 1: Generate Secret & QR URI.
    User scans this on their phone.
    """
    # Extract user email from token (assuming it's in there or we fetch it)
    # For simplicity, using a placeholder, but you should fetch user profile
    return service.generate_secret(email="user@example.com")


@router.post("/verify", response_model=MfaMethodResponse)
async def verify_and_enable_mfa(
        data: MfaVerifyRequest,
        request: Request,
        service: MfaService = Depends(get_mfa_service)
):
    """
    Step 2: User sends the code from their phone.
    We verify and save it.
    """
    # Extract User ID and Tenant ID from the current Auth Token
    token = request.headers.get("Authorization").split(" ")[1]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    user_id = payload.get("sub")
    tenant_id = payload.get("tid")

    # Verify code and save
    mfa_method = await service.setup_totp(user_id, tenant_id, data.secret, data.code)

    # Enable it immediately
    return await service.enable_totp(mfa_method.mfa_id)