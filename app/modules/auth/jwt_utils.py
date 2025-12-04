# app/modules/auth/jwt_utils.py

import jwt
from fastapi import HTTPException, status
from app.core.config import settings
from app.modules.auth.token_blacklist import TokenBlacklistRepository
from app.core.database import db


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


async def verify_token_not_blacklisted(jti: str):
    async for conn in db.get_connection("00000000-0000-0000-0000-000000000000"):
        repo = TokenBlacklistRepository(conn)
        if await repo.is_token_blacklisted(jti):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked"
            )
