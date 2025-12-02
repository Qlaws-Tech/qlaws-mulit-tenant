# app/modules/auth/router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status

from app.dependencies.database import get_db_connection
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.core.security import get_bearer_token

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


# -------------------------------------------------------
# Dependency factory for AuthService
# -------------------------------------------------------
async def get_auth_service(conn=Depends(get_db_connection)) -> AuthService:
    return AuthService(conn)


# -------------------------------------------------------
# LOGIN
# -------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")
    return await svc.login(body, ip_address=ip, user_agent=ua)


# -------------------------------------------------------
# REFRESH TOKENS
# -------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    refresh_token: str,  # comes from query param: ?refresh_token=...
    svc: AuthService = Depends(get_auth_service),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing refresh_token",
        )
    return await svc.refresh_tokens(refresh_token)


# -------------------------------------------------------
# LOGOUT
# -------------------------------------------------------
@router.post("/logout")
async def logout(
    request: Request,
    svc: AuthService = Depends(get_auth_service),
):
    # Access token comes from Authorization: Bearer <token>
    token = get_bearer_token(request)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")

    await svc.logout(token, ip_address=ip, user_agent=ua)
    return {"detail": "Logged out"}
