# app/modules/sso/service.py

from typing import List
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.sso.schemas import (
    SSOProviderCreate,
    SSOProviderUpdate,
    SSOProviderResponse,
)
from app.modules.sso.repository import SSOProviderRepository
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate


class SSOService:
    def __init__(self, conn):
        self.conn = conn
        self.repo = SSOProviderRepository(conn)
        self.audit_repo = AuditRepository(conn)

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    async def create_provider(self, payload: SSOProviderCreate) -> SSOProviderResponse:
        provider = await self.repo.create(payload)

        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="sso.create",
                resource_type="sso_provider",
                resource_id=str(provider.sso_provider_id),
                details={"name": provider.name, "provider_type": provider.provider_type},
            )
        )
        # On create, we return plaintext config (for UI to confirm)
        return provider

    # ---------------------------------------------------------
    # LIST
    # ---------------------------------------------------------
    async def list_providers(self) -> List[SSOProviderResponse]:
        providers = await self.repo.list_providers()
        # Mask secrets in listing
        for p in providers:
            if "client_secret" in p.config:
                p.config["client_secret"] = "********"
        return providers

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------
    async def update_provider(
        self,
        provider_id: UUID,
        payload: SSOProviderUpdate,
    ) -> SSOProviderResponse:
        updated = await self.repo.update(provider_id, payload)
        if not updated:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO provider not found")

        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="sso.update",
                resource_type="sso_provider",
                resource_id=str(provider_id),
                details=payload.dict(exclude_unset=True),
            )
        )
        # For update, also return plaintext config
        return updated

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------
    async def delete_provider(self, provider_id: UUID):
        existing = await self.repo.get_by_id(provider_id)
        if not existing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO provider not found")

        await self.repo.delete(provider_id)

        await self.audit_repo.log_event(
            AuditLogCreate(
                action_type="sso.delete",
                resource_type="sso_provider",
                resource_id=str(provider_id),
                details={"name": existing.name},
            )
        )
