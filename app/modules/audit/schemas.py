from pydantic import BaseModel, UUID4, Field, IPvAnyAddress
from typing import Optional, Dict, Any
from datetime import datetime

class AuditLogCreate(BaseModel):
    action_type: str        # e.g., "user.login", "tenant.create"
    actor_user_id: Optional[UUID4] = None # Who did it?
    resource_type: str      # e.g., "user", "tenant"
    resource_id: str        # ID of the object affected
    details: Dict[str, Any] = Field(default_factory=dict) # Metadata
    ip_address: Optional[str] = None

class AuditLogResponse(BaseModel):
    event_time: datetime
    actor_user_id: Optional[UUID4]
    action_type: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True