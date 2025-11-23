from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import uuid
import hashlib
import json
import pyotp
from jose import jwt
from config_dev import settings
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.email import send_email  # <-- Integrated Email Service
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import MfaRequiredResponse


class AuthService:
    # --- Login with MFA Interception ---
    async def authenticate_user(self, conn, email: str, password: str, tenant_id: str, ip: str, user_agent: str):
        # 1. Enforce RLS Context
        try:
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Tenant ID")

        # 2. Fetch User
        row = await conn.fetchrow(
            """
            SELECT u.user_id, u.hashed_password, ut.status, ut.user_tenant_id
            FROM user_tenants ut
            JOIN users u ON ut.user_id = u.user_id
            WHERE ut.tenant_email = $1
            """,
            email
        )

        if not row or not verify_password(password, row['hashed_password']):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if row['status'] != 'active':
            raise HTTPException(status_code=403, detail="User is inactive")

        repo = AuthRepository(conn)

        # 3. MFA Enforcement Check
        if await repo.is_mfa_enabled(str(row['user_id'])):
            # Generate short-lived Pre-Auth Token
            pre_auth_token = self._create_pre_auth_token(row['user_id'], tenant_id)
            return MfaRequiredResponse(pre_auth_token=pre_auth_token)

        # 4. Standard Login (No MFA)
        return await self._finalize_login(repo, row['user_id'], row['user_tenant_id'], tenant_id, ip, user_agent)

    # --- MFA Verification Step 2 ---
    async def verify_mfa_login(self, conn, pre_auth_token: str, code: str, ip: str, user_agent: str):
        # 1. Decode Pre-Auth Token
        try:
            payload = jwt.decode(pre_auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") != "pre_auth":
                raise Exception("Invalid token type")
            user_id = payload.get("sub")
            tenant_id = payload.get("tid")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired pre-auth session")

        # 2. Verify OTP
        repo = AuthRepository(conn)
        # Temporarily set context to fetch MFA secret
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))

        secret = await repo.get_totp_secret(user_id)
        if not secret:
            raise HTTPException(400, detail="MFA configuration invalid")

        totp = pyotp.TOTP(secret)
        if not totp.verify(code):
            raise HTTPException(401, detail="Invalid OTP code")

        # 3. Finalize Login
        ut_row = await conn.fetchrow(
            "SELECT user_tenant_id FROM user_tenants WHERE user_id=$1::uuid AND tenant_id=$2::uuid", user_id, tenant_id)

        return await self._finalize_login(repo, uuid.UUID(user_id), ut_row['user_tenant_id'], tenant_id, ip, user_agent)

    # --- Helpers ---
    def _create_pre_auth_token(self, user_id, tenant_id):
        expire = datetime.now(timezone.utc) + timedelta(minutes=5)
        to_encode = {"sub": str(user_id), "tid": str(tenant_id), "type": "pre_auth", "exp": expire}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def _finalize_login(self, repo, user_id, user_tenant_id, tenant_id, ip, ua):
        # RLS Compliance: Pass tenant_id (str) to match current session context
        session_id = await repo.create_session(user_tenant_id, tenant_id, ip, ua)

        tenant_id_str = str(tenant_id)
        access_token = create_access_token(subject=user_id, tenant_id=tenant_id_str)

        raw_refresh = str(uuid4()) + str(uuid4())
        refresh_hash = hashlib.sha256(raw_refresh.encode()).hexdigest()
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        await repo.create_refresh_token(session_id, refresh_hash, refresh_expires)

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "token_type": "bearer"
        }

    # --- Token Rotation ---
    async def rotate_tokens(self, conn, refresh_token: str, ip: str, user_agent: str):
        repo = AuthRepository(conn)
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        data = await repo.get_refresh_token_data(token_hash)
        if not data:
            raise HTTPException(401, "Invalid refresh token")

        # Security Check: Ensure session hasn't been revoked remotely
        if data['revoked'] or data['session_revoked'] or data['expires_at'] < datetime.now(timezone.utc):
            raise HTTPException(401, "Token or Session expired/revoked")

        await repo.revoke_refresh_token(data['refresh_id'])

        tenant_id_str = str(data['tenant_id'])
        new_access = create_access_token(subject=data['user_id'], tenant_id=tenant_id_str)

        new_raw_refresh = str(uuid4()) + str(uuid4())
        new_hash = hashlib.sha256(new_raw_refresh.encode()).hexdigest()
        new_expires = datetime.now(timezone.utc) + timedelta(days=7)

        await repo.create_refresh_token(data['session_id'], new_hash, new_expires)

        return {
            "access_token": new_access,
            "refresh_token": new_raw_refresh,
            "token_type": "bearer"
        }

    # --- Session Management ---
    async def list_sessions(self, conn, user_id: str):
        repo = AuthRepository(conn)
        sessions = await repo.list_user_sessions(user_id)
        for s in sessions:
            # Handle JSON Parsing
            if isinstance(s.get('device_info'), str):
                try:
                    s['device_info'] = json.loads(s['device_info'])
                except json.JSONDecodeError:
                    s['device_info'] = {}
                    # Handle IP conversion for Pydantic
            if s.get('ip_address'):
                s['ip_address'] = str(s['ip_address'])
        return sessions

    async def revoke_session(self, conn, session_id: str, user_id: str):
        repo = AuthRepository(conn)
        await repo.revoke_session(session_id, user_id)

    # --- Logout ---
    async def logout_user(self, conn, jti: str, tenant_id: str, exp_timestamp: int):
        repo = AuthRepository(conn)
        if not exp_timestamp:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        else:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        await repo.revoke_token(jti, tenant_id, expires_at)

    # --- Password Reset ---
    async def request_password_reset(self, conn, email: str):
        user = await conn.fetchrow("SELECT user_id FROM users WHERE primary_email = $1", email)

        # Security: Always return a "success" signal (None or token) to prevent Email Enumeration
        if not user:
            return None

        reset_token = str(uuid4())
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        repo = AuthRepository(conn)
        await repo.create_reset_token(str(user['user_id']), token_hash, expires_at)

        # Email Delivery
        link = f"https://app.qlaws.com/reset?token={reset_token}"
        body = f"Click here to reset your password: {link}"

        try:
            await send_email("Password Reset Request", email, body)
        except Exception as e:
            # Log error but don't crash the request
            print(f"Failed to send email: {e}")

        return reset_token  # Only for testing convenience

    async def reset_password(self, conn, token: str, new_password: str):
        repo = AuthRepository(conn)
        lookup_hash = hashlib.sha256(token.encode()).hexdigest()

        record = await repo.get_valid_reset_token(lookup_hash)
        if not record:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        new_pw_hash = get_password_hash(new_password)

        async with conn.transaction():
            await repo.update_password(record['user_id'], new_pw_hash)
            await repo.mark_token_used(record['reset_id'])