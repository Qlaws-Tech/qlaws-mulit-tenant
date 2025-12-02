# app/modules/auth/mfa/router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from jose import jwt, JWTError
from uuid import UUID

from app.core.config import settings
from app.dependencies.database import get_tenant_db_connection
from app.modules.auth.mfa.repository import MFARepository
from app.modules.auth.mfa.service import MFAService
from app.modules.auth.mfa.schemas import MFAEnrollRequest, MFAEnrollResponse

router = APIRouter(tags=["MFA"])


async def get_mfa_service(conn = Depends(get_tenant_db_connection)) -> MFAService:
    repo = MFARepository(conn)
    return MFAService(repo, conn)


def _extract_user_and_tenant_from_auth(request: Request) -> tuple[UUID, UUID]:
    """
    Lightweight auth helper:
    - Reads Bearer token
    - Decodes JWT with SECRET_KEY/ALGORITHM
    - Returns (user_id, tenant_id)
    Raises 401 on any issue.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(status_code=401, detail="Missing Authorization")

    try:
        scheme, token = auth.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    sub = payload.get("sub")
    tid = payload.get("tid")
    if not sub or not tid:
        raise HTTPException(status_code=401, detail="Malformed token")

    try:
        user_id = UUID(sub)
        tenant_id = UUID(tid)
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed token subject/tenant")

    return user_id, tenant_id


@router.post("/enroll", response_model=MFAEnrollResponse)
async def enroll_mfa_device(
    request: Request,
    body: MFAEnrollRequest,
    service: MFAService = Depends(get_mfa_service),
):
    """
    Enroll an MFA device for the currently authenticated user.
    Test `test_mfa_device_registration_flow` hits this with:
      POST /api/v1/mfa/enroll
      body={"device_type": "totp", "device_name": "Authy"}
    and checks that `device_id` exists in the response.
    """
    user_id, tenant_id = _extract_user_and_tenant_from_auth(request)
    resp = await service.enroll_device(user_id, tenant_id, body)
    return resp
