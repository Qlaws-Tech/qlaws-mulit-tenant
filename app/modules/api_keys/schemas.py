# app/modules/api_keys/schemas.py

from pydantic import BaseModel, Field
from typing import List
from uuid import UUID
from datetime import datetime


class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str] = Field(default_factory=list)


class ApiKeyResponse(BaseModel):
    api_key_id: UUID
    name: str
    scopes: List[str]
    created_at: datetime


class ApiKeyWithPlain(ApiKeyResponse):
    plain_key: str


class ApiKeyInfo(BaseModel):
    api_key_id: UUID
    tenant_id: UUID
    scopes: List[str]
