from pydantic import BaseModel, Field, UUID4
from typing import List, Optional
from datetime import datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, description="e.g. 'Okta SCIM'")
    scopes: List[str] = Field(default_factory=list, description="e.g. ['scim.write', 'audit.read']")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    api_key_id: UUID4
    name: str
    prefix: str  # We only show the prefix (first 8 chars)
    scopes: List[str]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(ApiKeyResponse):
    plain_key: str  # CRITICAL: Only returned ONCE upon creation