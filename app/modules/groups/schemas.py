# app/modules/groups/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    """
    Optional updates for a group.
    Currently not used heavily, but kept for compatibility with routers/tests.
    """
    name: Optional[str] = None
    description: Optional[str] = None


class GroupRolesUpdate(BaseModel):
    """
    Placeholder for updating roles associated with a group.
    If you don’t yet support group→role mapping, you can ignore this in the service.
    """
    role_ids: List[UUID]


class GroupResponse(BaseModel):
    group_id: UUID
    name: str
    description: Optional[str]
    member_count: int
    created_at: datetime
