from pydantic import BaseModel, EmailStr, UUID4, Field
from typing import Optional, Dict, Any, Union
from datetime import datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: UUID4

# --- MFA Enforcement Schemas (NEW) ---
class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    pre_auth_token: str
    message: str = "MFA verification required"

class MfaLoginVerifyRequest(BaseModel):
    pre_auth_token: str
    code: str

# Combined Login Response
LoginResponse = Union[Token, MfaRequiredResponse]

# --- Password Management Schemas ---
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

# --- Session Schemas ---
class SessionResponse(BaseModel):
    session_id: UUID4
    ip_address: Optional[str]
    device_info: Optional[Dict[str, Any]]
    last_seen_at: datetime
    created_at: datetime
    is_current: bool = False

    class Config:
        from_attributes = True