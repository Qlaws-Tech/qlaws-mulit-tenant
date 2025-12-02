# app/modules/audit/schemas.py
import json

from pydantic import BaseModel, Field, field_validator, IPvAnyAddress
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class AuditLogCreate(BaseModel):
    action_type: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any] = {}


class AuditLogEntry(BaseModel):


    audit_id: UUID
    tenant_id: UUID
    actor_user_id: Optional[UUID]
    action_type: str
    resource_type: str
    resource_id: str
    ip_address: Optional[IPvAnyAddress] = None
    created_at: datetime
    details: Optional[Dict[str, Any]] = None

    @field_validator("details", mode="before")
    @classmethod
    def parse_details(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            # DB returns JSON as text -> parse it
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # fallback: keep raw value or wrap it
                return {"raw": v}
        return v


# --- Missing Models Added Below ---

class AuditQuery(BaseModel):
    """
    Filters for querying audit logs.
    """
    action_type: Optional[str] = None
    resource_type: Optional[str] = None
    actor_user_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


# Alias AuditLogResponse to AuditLogEntry for now,
# but keeping it distinct allows for future expansion (e.g. creating links/meta).
class AuditLogResponse(AuditLogEntry):
    pass


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]