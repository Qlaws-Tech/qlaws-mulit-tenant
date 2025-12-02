# app/modules/sso/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class SSOProviderConfig(BaseModel):
    # For OIDC – you can extend this for SAML later
    client_id: str
    client_secret: str
    issuer_url: str
    # extra fields are allowed for future providers
    extra: Dict[str, Any] = Field(default_factory=dict)


class SSOProviderCreate(BaseModel):
    # changed: regex -> pattern for Pydantic v2
    provider_type: str = Field(
        ...,
        description="oidc or saml",
        pattern="^(oidc|saml)$",
    )
    name: str
    description: Optional[str] = None
    enabled: bool = True
    config: Dict[str, Any]


class SSOProviderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class SSOProviderResponse(BaseModel):
    sso_provider_id: UUID
    provider_type: str
    name: str
    description: Optional[str]
    enabled: bool
    config: Dict[str, Any]
    created_at: datetime
