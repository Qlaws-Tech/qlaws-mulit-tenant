# app/modules/tenants/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from enum import Enum
from datetime import datetime


class TenantPlan(str, Enum):
    free = "free"
    startup = "startup"
    pro = "pro"
    enterprise = "enterprise"


class TenantCreate(BaseModel):
    """
    Payload used by POST /api/v1/tenants/.
    Tests expect:
      - name
      - plan (must be a valid enum -> invalid => 422)
      - admin_email
      - admin_password
      - admin_name
    We also support domain/region for real app usage.
    """
    model_config = ConfigDict(from_attributes=True)
    name: str = Field(..., min_length=2)
    domain: Optional[str] = None
    plan: TenantPlan = TenantPlan.startup
    region: Optional[str] = None

    admin_email: str
    admin_password: str
    admin_name: str


class TenantResponse(BaseModel):
    """
    General tenant info (for listing / detail).
    """
    tenant_id: UUID
    name: str
    domain: Optional[str]
    plan: TenantPlan
    region: Optional[str] = None
    status: str
    created_at: datetime


class TenantOnboardingResponse(BaseModel):
    """
    Response shape used by service tests.
    """
    model_config = ConfigDict(from_attributes=True)
    tenant_id: UUID
    admin_email: str
