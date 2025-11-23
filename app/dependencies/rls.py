from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from asyncpg import Connection
from app.dependencies.database import get_db_connection
from app.modules.auth.repository import AuthRepository
from app.core.auth_strategy import TokenVerifier

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_tenant_db_connection(
        token: str = Depends(oauth2_scheme),
        conn: Connection = Depends(get_db_connection)
) -> Connection:
    """
    1. Verifies Token (Local or External based on Config).
    2. Checks Local Blacklist (Only applies if JTI is present).
    3. Sets RLS Context.
    """
    # 1. Verify Token (Strategy Pattern)
    # This handles HS256 (Local) vs RS256 (Auth0/Okta) logic transparently via config
    payload = await TokenVerifier.verify(token)

    tenant_id = payload.get("tid")
    jti = payload.get("jti")

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is valid but missing Tenant ID (tid) context",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Check Blacklist (Optional for External, Mandatory for Local)
    # Only check if the token has a JTI (Local tokens always do).
    # External providers manage their own revocation, but we can blacklist specific JTI if needed.
    if jti:
        auth_repo = AuthRepository(conn)
        if await auth_repo.is_token_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. Set RLS Context
    try:
        await conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            str(tenant_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RLS Context Error: {str(e)}")

    # Yield OUTSIDE the try block so application errors (e.g. 404, Validation)
    # don't get caught as RLS errors.
    yield conn