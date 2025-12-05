# app/modules/auth/password_reset_service.py

from fastapi import HTTPException, status
from pydantic import UUID4

from app.modules.users.repository import UserRepository
from app.modules.auth.repository import AuthRepository
from app.core.security import hash_password


class PasswordResetService:
    def __init__(self, conn):
        self.conn = conn
        self.user_repo = UserRepository(conn)
        self.auth_repo = AuthRepository(conn)

    async def request_reset(self, email: str):
        user = await self.auth_repo.get_user_by_email(email)
        if not user:
            return {"message": "If the email exists, a reset link will be sent."}

        token = await self._create_reset_token(UUID4(user.user_id))

        return {"debug_token": token}

    async def _create_reset_token(self, user_id: str):
        import uuid, hashlib
        plain = str(uuid.uuid4())
        hashed = hashlib.sha256(plain.encode()).hexdigest()

        await self.conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, now() + interval '1 hour')
            """,
            user_id, hashed
        )
        return plain

    async def reset_password(self, token: str, new_password: str):
        import hashlib
        hashed = hashlib.sha256(token.encode()).hexdigest()

        row = await self.conn.fetchrow(
            """
            SELECT user_id FROM password_reset_tokens
            WHERE token_hash = $1 AND expires_at > now()
            """,
            hashed
        )
        if not row:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

        await self.user_repo.update_password(row["user_id"], hash_password(new_password))

        return {"message": "Password updated"}
