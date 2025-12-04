from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class UserCreate(BaseModel):
    """
    Payload used to create a user (tenant admin, normal users, etc.).
    """
    model_config = ConfigDict(from_attributes=True)
    email: str
    password: str = Field(min_length=8)
    display_name: str
    # NEW: optional persona like "Partner", "Paralegal", etc.
    persona: Optional[str] = None


class UserUpdate(BaseModel):
    """
    Partial update for a user. All fields optional.
    """
    model_config = ConfigDict(from_attributes=True)
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    display_name: Optional[str] = None
    # NEW: allow updating persona
    persona: Optional[str] = None
    # you can extend with more optional fields later (status, locale, etc.)


class UserInDB(BaseModel):
    """
    Minimal representation of a user as stored in the DB.
    Used internally in repositories/services.
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    tenant_id: UUID
    email: str
    display_name: str
    created_at: datetime


class UserContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    email: str
    display_name: str
    tenant_id: UUID
    tenant_name: str
    roles: List[str]
    permissions: List[str] = Field(default_factory=list)
    # NEW: persona on the tenant membership
    persona: Optional[str] = None


class UserResponse(BaseModel):
    """
    Generic user response model used by user CRUD endpoints (/users list, etc.).
    Existing imports `from app.modules.users.schemas import UserResponse`
    will resolve to this.
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    tenant_id: UUID
    email: str
    display_name: str
    created_at: Optional[datetime] = None

    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    # NEW: persona included in list/detail responses
    persona: Optional[str] = None


class CurrentUserResponse(BaseModel):
    """
    Response for the 'current user' endpoint.
    Typically used for /api/v1/users/me or similar.
    It’s a superset of UserProfileResponse including the user_id.
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    tenant_id: UUID
    email: str
    display_name: str
    tenant_name: str

    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    # NEW: persona for current user
    persona: Optional[str] = None

    redirect_url: str
