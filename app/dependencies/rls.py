# app/dependencies/rls.py

from uuid import UUID
from fastapi import Request, HTTPException, status
from jose import jwt, JWTError

from app.core.config import settings


async def tenant_context_middleware(request: Request, call_next):
    """
    Best-effort middleware to populate request.state.tenant_id.

    Priority:
    1) X-Tenant-ID header (explicit override)
    2) JWT 'tid' claim (for authenticated calls)

    Also ensures that if BOTH header and token have a tenant,
    they do not conflict.
    """

    header_tid: UUID | None = None
    token_tid: UUID | None = None

    # 1) X-Tenant-ID header
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header:
        try:
            header_tid = UUID(tenant_header)
            request.state.tenant_id = header_tid
        except ValueError:
            # Ignore invalid UUID in header
            pass

    # 2) JWT 'tid' claim
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            tid = payload.get("tid")
            if tid:
                try:
                    token_tid = UUID(tid)
                except ValueError:
                    token_tid = None

                # If we didn't already set tenant_id from header, use token
                if not hasattr(request.state, "tenant_id"):
                    request.state.tenant_id = token_tid

        except (JWTError, ValueError):
            # Ignore; some endpoints are public (e.g. invitation accept, password reset)
            pass

    # 3) If both header and token tenant IDs exist and conflict → error
    if header_tid and token_tid and header_tid != token_tid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant mismatch: header and token differ",
        )

    response = await call_next(request)
    return response
