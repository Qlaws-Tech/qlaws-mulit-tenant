# app/modules/roles/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None
    permission_keys: List[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_keys: Optional[List[str]] = None


class RoleResponse(BaseModel):
    role_id: UUID
    name: str
    description: Optional[str]
    permissions: List[str]
    created_at: datetime
