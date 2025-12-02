# app/modules/auth/service.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from asyncpg import Connection

from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_access_token,
    datetime_from_timestamp,
)
from app.core.config import settings


class AuthService:
    """
    Authentication service:
    - login via email/password + tenant_id
    - refresh tokens using refresh token
    - logout via access token (blacklisting)
    """

    def __init__(self, conn: Connection):
        self.conn = conn
        self.auth_repo = AuthRepository(conn)
        self.audit_repo = AuditRepository(conn)

    # ------------------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------------------
    async def login(
        self,
        payload: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenResponse:
        tenant_id: UUID = payload.tenant_id

        # 1) Set RLS tenant context *for this connection*.
        await self.conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            str(tenant_id),
        )

        # 2) Fetch user + tenant membership
        user_row = await self.auth_repo.get_user_for_login(
            tenant_id=tenant_id,
            email=payload.email,
        )

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found for this tenant",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user_row.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not active for this tenant",
            )

        # 3) Verify password
        if not verify_password(payload.password, user_row["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = user_row["user_id"]

        # 4) Create tokens
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        access_token = create_access_token(
            data={
                "sub": str(user_id),
                "tid": str(tenant_id),
            },
            expires_delta=access_token_expires,
        )

        refresh_token = create_refresh_token(
            data={
                "sub": str(user_id),
                "tid": str(tenant_id),
            }
        )

        # 5) Audit successful login
        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="auth.login",
                resource_type="user",
                resource_id=str(user_id),
                details={
                    "tenant_id": str(tenant_id),
                    "ip_address": ip_address,
                    "user_agent": user_agent or "",
                },
            ),
            actor_user_id=user_id,
            ip_address=ip_address,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ------------------------------------------------------------------
    # REFRESH TOKENS
    # ------------------------------------------------------------------
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Exchange a valid refresh token for a new access + refresh pair.
        """
        payload = decode_token(refresh_token, verify_exp=True)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        token_type = payload.get("type")
        if token_type and token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for refresh",
            )

        user_id = payload.get("sub")
        tenant_id = payload.get("tid") or payload.get("tenant_id")

        if not user_id or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing subject or tenant",
            )

        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        new_access = create_access_token(
            data={"sub": str(user_id), "tid": str(tenant_id)},
            expires_delta=access_token_expires,
        )
        new_refresh = create_refresh_token(
            data={"sub": str(user_id), "tid": str(tenant_id)}
        )

        return TokenResponse(
            access_token=new_access,
            token_type="bearer",
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ------------------------------------------------------------------
    # LOGOUT
    # ------------------------------------------------------------------
    async def logout(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Logout by blacklisting the *access token*.

        Matches DB schema:
          token_blacklist(
            jti TEXT PRIMARY KEY NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            tenant_id UUID,
            user_id UUID,
            token_hash TEXT,
            expires_at TIMESTAMPTZ NOT NULL
          )
        """

        payload = decode_token(token, verify_exp=False)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        user_id = payload.get("sub")
        tenant_id = payload.get("tid") or payload.get("tenant_id")
        exp_ts = payload.get("exp")

        if not user_id or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject or tenant",
            )

        # Ensure tenant context is set for audit logs
        await self.conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            str(tenant_id),
        )

        # Determine expiry for blacklist entry
        if exp_ts is not None:
            try:
                expires_at = datetime_from_timestamp(exp_ts)
            except Exception:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        # Use a hash of the access token as both jti and token_hash
        token_hash = hash_access_token(token)
        jti = token_hash

        await self.conn.execute(
            """
            INSERT INTO token_blacklist (jti, token_hash, tenant_id, user_id, expires_at)
            VALUES ($1, $2, $3::uuid, $4::uuid, $5)
            ON CONFLICT (jti) DO UPDATE
               SET token_hash = EXCLUDED.token_hash,
                   tenant_id  = EXCLUDED.tenant_id,
                   user_id    = EXCLUDED.user_id,
                   expires_at = EXCLUDED.expires_at
            """,
            jti,
            token_hash,
            str(tenant_id),
            str(user_id),
            expires_at,
        )

        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="auth.logout",
                resource_type="user",
                resource_id=str(user_id),
                details={
                    "tenant_id": str(tenant_id),
                    "ip_address": ip_address,
                    "user_agent": user_agent or "",
                },
            ),
            actor_user_id=user_id,
            ip_address=ip_address,
        )

        return {"detail": "Logged out"}
