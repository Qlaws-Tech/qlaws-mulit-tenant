# app/modules/auth/mfa/service.py

import secrets
from uuid import UUID
from typing import List

from app.modules.auth.mfa.repository import MFARepository
from app.modules.auth.mfa.schemas import (
    MFAEnrollRequest,
    MFAEnrollResponse,
    MFADeviceResponse,
)


class MFAService:
    """
    High-level MFA orchestration.
    """

    def __init__(self, repo: MFARepository, conn):
        self.repo = repo
        self.conn = conn

    async def enroll_device(
        self,
        user_id: UUID,
        tenant_id: UUID,
        payload: MFAEnrollRequest,
    ) -> MFAEnrollResponse:

        secret = secrets.token_hex(16)
        return await self.repo.create_method(user_id, tenant_id, payload, secret)

    async def list_devices(self, user_id: UUID, tenant_id: UUID) -> List[MFADeviceResponse]:
        return await self.repo.list_methods(user_id, tenant_id)

    # verify / delete could be added as needed
