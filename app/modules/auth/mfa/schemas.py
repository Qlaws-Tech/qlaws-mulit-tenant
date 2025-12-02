# app/modules/auth/mfa/schemas.py

from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime


class MFAEnrollRequest(BaseModel):
    """
    Request body to enroll a new MFA device.
    Tests send:
      {"device_type": "totp", "device_name": "Authy"}
    """
    device_type: Literal["totp"] = Field(..., description="MFA method type, currently only 'totp'")
    device_name: str = Field(..., min_length=1)


class MFAEnrollResponse(BaseModel):
    """
    Response after enrolling an MFA device.
    """
    device_id: UUID
    device_type: str
    device_name: str
    secret: str  # TOTP secret (e.g., to show QR code)
    enabled: bool
    created_at: datetime


class MFAVerifyRequest(BaseModel):
    """
    Request to verify an MFA code.
    Not used by current tests, but included for completeness.
    """
    device_id: UUID
    code: str = Field(..., min_length=3, max_length=12)


class MFADeviceResponse(BaseModel):
    """
    Generic representation of an MFA device (no secret).
    """
    device_id: UUID
    device_type: str
    device_name: str
    enabled: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
