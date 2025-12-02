from uuid import UUID

from pydantic import BaseModel, UUID4, Field, ConfigDict
from typing import Optional, Any, Dict
from datetime import datetime


# ---------- Core Auth Schemas ----------

class LoginRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    password: str = Field(..., min_length=6)
    tenant_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


# ---------- Sessions ----------

class SessionResponse(BaseModel):
    session_id: UUID
    user_tenant_id: UUID
    tenant_id: UUID
    ip_address: Optional[str] = None
    device_info: Optional[dict[str, Any]] = None
    revoked: bool
    last_seen_at: datetime
    created_at: datetime


# ---------- Password Reset ----------

class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    tenant_id: UUID4


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (already validated by frontend policy)",
    )

class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SessionRead(BaseModel):
    session_id: str
    user_id: str
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    expires_at: datetime
