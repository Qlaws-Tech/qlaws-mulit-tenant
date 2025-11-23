from pydantic import BaseModel, Field, EmailStr, UUID4
from typing import Optional, Dict, Any
from datetime import datetime


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2)
    domain: Optional[str] = None
    plan: str = Field("startup", pattern="^(startup|enterprise)$")
    region: str = Field("us-east-1")
    config: Dict[str, Any] = {}

    # --- NEW: Admin Fields for Onboarding ---
    admin_email: str
    admin_password: str = Field(..., min_length=8)
    admin_name: str


class TenantResponse(BaseModel):
    tenant_id: UUID4
    name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TenantOnboardingResponse(TenantResponse):
    # Returns Tenant info + Initial Admin info
    admin_email: str
    message: str = "Tenant and Admin created successfully"