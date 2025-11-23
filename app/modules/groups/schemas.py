from pydantic import BaseModel, UUID4, Field
from typing import List, Optional
from datetime import datetime

# --- Core Group Schemas ---
class GroupBase(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None

class GroupCreate(GroupBase):
    pass

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class GroupResponse(GroupBase):
    group_id: UUID4
    created_at: datetime
    member_count: int = 0  # Computed field
    roles: List[str] = []  # List of role names assigned to this group

    class Config:
        from_attributes = True

# --- Action Schemas ---
class AddMemberRequest(BaseModel):
    user_id: UUID4  # We accept user_id (global), but map to user_tenant_id internally

class AssignRoleRequest(BaseModel):
    role_id: UUID4