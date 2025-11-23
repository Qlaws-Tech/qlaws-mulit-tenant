from asyncpg import Connection
from datetime import datetime
from uuid import UUID
from typing import List, Optional
import json


class AuthRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # --- MFA Checks (Required for Login Interception) ---
    async def is_mfa_enabled(self, user_id: str) -> bool:
        """
        Checks if the user has an active MFA method.
        """
        query = """
            SELECT 1 FROM mfa_methods 
            WHERE user_id = $1::uuid AND enabled = true
            LIMIT 1
        """
        return await self.conn.fetchval(query, str(user_id)) is not None

    async def get_totp_secret(self, user_id: str) -> Optional[str]:
        """
        Fetches the encrypted secret for TOTP verification.
        """
        query = """
            SELECT metadata->>'secret' as secret 
            FROM mfa_methods 
            WHERE user_id = $1::uuid AND method_type = 'totp' AND enabled = true
        """
        return await self.conn.fetchval(query, str(user_id))

    # --- Token Blacklist (Logout) ---
    async def revoke_token(self, jti: str, tenant_id: str, expires_at: datetime):
        query = """
            INSERT INTO token_blacklist (jti, tenant_id, expires_at)
            VALUES ($1, $2::uuid, $3)
        """
        await self.conn.execute(query, jti, tenant_id, expires_at)

    async def is_token_revoked(self, jti: str) -> bool:
        query = "SELECT 1 FROM token_blacklist WHERE jti = $1"
        return await self.conn.fetchval(query, jti) is not None

    # --- Session Management ---
    async def create_session(self, user_tenant_id: UUID, tenant_id: str, ip: str, ua: str) -> UUID:
        # Use json.dumps to ensure valid JSONB format
        device_info = json.dumps({"user_agent": ua})

        query = """
            INSERT INTO sessions (user_tenant_id, tenant_id, ip_address, device_info, created_at, last_seen_at)
            VALUES ($1, $2::uuid, $3::inet, $4::jsonb, now(), now())
            RETURNING session_id
        """
        return await self.conn.fetchval(query, user_tenant_id, tenant_id, ip, device_info)

    async def create_refresh_token(self, session_id: UUID, token_hash: str, expires_at: datetime):
        query = """
            INSERT INTO refresh_tokens (session_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
        """
        await self.conn.execute(query, session_id, token_hash, expires_at)

    async def get_refresh_token_data(self, token_hash: str):
        """
        Fetches refresh token data AND checks if the parent session is active.
        """
        query = """
            SELECT rt.refresh_id, rt.expires_at, rt.revoked,
                   s.session_id, s.tenant_id, s.user_tenant_id, s.revoked as session_revoked,
                   ut.user_id, ut.tenant_email as email, ut.status as user_status
            FROM refresh_tokens rt
            JOIN sessions s ON rt.session_id = s.session_id
            JOIN user_tenants ut ON s.user_tenant_id = ut.user_tenant_id
            WHERE rt.token_hash = $1
        """
        return await self.conn.fetchrow(query, token_hash)

    async def revoke_refresh_token(self, refresh_id: UUID):
        await self.conn.execute("UPDATE refresh_tokens SET revoked = true WHERE refresh_id = $1", refresh_id)

    async def list_user_sessions(self, user_id: str) -> List[dict]:
        query = """
            SELECT s.session_id, s.ip_address, s.device_info, s.last_seen_at, s.created_at
            FROM sessions s
            JOIN user_tenants ut ON s.user_tenant_id = ut.user_tenant_id
            WHERE ut.user_id = $1::uuid AND s.revoked = false
            ORDER BY s.last_seen_at DESC
        """
        rows = await self.conn.fetch(query, str(user_id))
        return [dict(row) for row in rows]

    async def revoke_session(self, session_id: str, user_id: str):
        """
        Revokes a session if it belongs to the user.
        """
        query = """
            UPDATE sessions s
            SET revoked = true
            FROM user_tenants ut
            WHERE s.user_tenant_id = ut.user_tenant_id
              AND s.session_id = $1::uuid
              AND ut.user_id = $2::uuid
        """
        await self.conn.execute(query, str(session_id), str(user_id))

    # --- Password Management ---
    async def create_reset_token(self, user_id: str, token_hash: str, expires_at: datetime):
        query = """
            INSERT INTO password_resets (user_id, token_hash, expires_at)
            VALUES ($1::uuid, $2, $3)
        """
        await self.conn.execute(query, user_id, token_hash, expires_at)

    async def get_valid_reset_token(self, token_hash: str):
        query = """
            SELECT reset_id, user_id, expires_at
            FROM password_resets
            WHERE token_hash = $1 
              AND used_at IS NULL 
              AND expires_at > now()
        """
        return await self.conn.fetchrow(query, token_hash)

    async def mark_token_used(self, reset_id: str):
        await self.conn.execute(
            "UPDATE password_resets SET used_at = now() WHERE reset_id = $1::uuid",
            str(reset_id)
        )

    async def update_password(self, user_id: str, hashed_password: str):
        await self.conn.execute(
            "UPDATE users SET hashed_password = $1, updated_at = now() WHERE user_id = $2::uuid",
            hashed_password, str(user_id)
        )