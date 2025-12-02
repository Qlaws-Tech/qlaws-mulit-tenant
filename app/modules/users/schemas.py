# app/modules/users/schemas.py

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


class UserUpdate(BaseModel):
    """
    Partial update for a user. All fields optional.
    """
    model_config = ConfigDict(from_attributes=True)
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    display_name: Optional[str] = None
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
    roles: List[str]          # <- NEW
    permissions: List[str] = None


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

    redirect_url: str

