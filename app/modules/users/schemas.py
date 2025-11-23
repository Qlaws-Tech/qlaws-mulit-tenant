from pydantic import BaseModel, EmailStr, UUID4, Field
from typing import Optional, List
from datetime import datetime


# --- Base User Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: str
    role: str = "member"


class UserUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|suspended)$")
    role: Optional[str] = None


class UserResponse(BaseModel):
    user_id: UUID4
    email: str
    display_name: str
    status: str
    tenant_role: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- NEW: User Context & Navigation Schema ---
class UserContextResponse(BaseModel):
    user_id: UUID4
    email: str
    display_name: str
    tenant_id: UUID4
    tenant_name: str
    # Security Profile
    roles: List[str]  # e.g., ["Admin", "Litigation_Lead"]
    permissions: List[str]  # e.g., ["doc.read", "user.create"] (Merged & Deduped)
    # Navigation
    redirect_url: str  # e.g., "/admin/dashboard" or "/workspace"

    class Config:
        from_attributes = True