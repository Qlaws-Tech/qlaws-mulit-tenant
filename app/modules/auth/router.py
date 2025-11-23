from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from typing import List
from config_dev import settings
from app.core.limiter import limiter  # <-- Import Rate Limiter
from app.dependencies.database import get_db_connection
from app.dependencies.rls import get_tenant_db_connection
from app.modules.auth.schemas import (
    LoginRequest, LoginResponse, Token, ForgotPasswordRequest,
    ResetPasswordRequest, SessionResponse, MfaLoginVerifyRequest
)
from app.modules.auth.service import AuthService

router = APIRouter()
service = AuthService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # <--- Rate Limit: 5 requests per minute per IP
async def login(
        request: Request,  # Required argument for slowapi limiter
        form_data: LoginRequest,
        conn=Depends(get_db_connection)
):
    """
    Step 1: Credential check.
    Returns either valid Tokens OR a request for MFA.
    Protected by Rate Limiting.
    """
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    return await service.authenticate_user(
        conn,
        form_data.email,
        form_data.password,
        str(form_data.tenant_id),
        client_ip,
        user_agent
    )


@router.post("/mfa/login-verify", response_model=Token)
@limiter.limit("5/minute")  # Rate limit MFA attempts as well
async def mfa_login_verify(
        request: Request,
        payload: MfaLoginVerifyRequest,
        conn=Depends(get_db_connection)
):
    """
    Step 2: Verify OTP to complete login (if Step 1 returned 'mfa_required').
    """
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    return await service.verify_mfa_login(
        conn, payload.pre_auth_token, payload.code, client_ip, user_agent
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
        refresh_token: str,
        request: Request,
        conn=Depends(get_db_connection)
):
    """Rotate tokens using a valid Refresh Token."""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")
    return await service.rotate_tokens(conn, refresh_token, client_ip, user_agent)


@router.post("/logout", status_code=204)
async def logout(
        token: str = Depends(oauth2_scheme),
        conn=Depends(get_db_connection)
):
    """Blacklists the current Access Token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        tid = payload.get("tid")
        exp = payload.get("exp")
        await service.logout_user(conn, jti, tid, exp)
    except Exception:
        pass
    return


@router.get("/sessions", response_model=List[SessionResponse])
async def list_my_sessions(
        token: str = Depends(oauth2_scheme),
        conn=Depends(get_tenant_db_connection)
):
    """View all active sessions for the current user."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return await service.list_sessions(conn, payload.get("sub"))


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_my_session(
        session_id: str,
        token: str = Depends(oauth2_scheme),
        conn=Depends(get_tenant_db_connection)
):
    """Revoke a specific session."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    await service.revoke_session(conn, session_id, payload.get("sub"))


@router.post("/forgot-password", status_code=202)
async def forgot_password(
        payload: ForgotPasswordRequest,
        conn=Depends(get_db_connection)
):
    token = await service.request_password_reset(conn, payload.email)
    # In production, remove 'debug_token' return value to prevent leakage
    return {"message": "If user exists, email sent.", "debug_token": token}


@router.post("/reset-password", status_code=200)
async def reset_password_confirm(
        payload: ResetPasswordRequest,
        conn=Depends(get_db_connection)
):
    await service.reset_password(conn, payload.token, payload.new_password)
    return {"message": "Password updated successfully."}