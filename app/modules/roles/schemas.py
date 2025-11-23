from pydantic import BaseModel, UUID4, Field
from typing import List, Optional
from datetime import datetime


# --- Permissions ---
class PermissionResponse(BaseModel):
    permission_id: UUID4
    key: str
    description: Optional[str]


# --- Roles ---
class RoleBase(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    # When creating a role, we might pass a list of permission keys (e.g., ["doc.read", "case.edit"])
    permission_keys: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_keys: Optional[List[str]] = None  # If provided, replaces existing permissions


class RoleResponse(RoleBase):
    role_id: UUID4
    is_builtin: bool
    permissions: List[str] = []  # List of keys
    created_at: datetime

    class Config:
        from_attributes = True