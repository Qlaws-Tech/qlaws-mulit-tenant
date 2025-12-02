# app/modules/scim/repository.py

from typing import Optional
from uuid import UUID, uuid4
from asyncpg import Connection

from app.modules.scim.schemas import SCIMUserCreate, SCIMUserResponse, SCIMName, SCIMEmail, SCIMMeta
from app.modules.users.repository import UserRepository
from app.core.security import get_password_hash


class SCIMRepository:
    """
    SCIM provisioning repository.

    - Creates internal users & user_tenants.
    - Tracks mapping in scim_mappings.
    """

    def __init__(self, conn: Connection):
        self.conn = conn
        self.user_repo = UserRepository(conn)

    async def create_scim_user(self, payload: SCIMUserCreate, tenant_id: UUID, base_url: str) -> SCIMUserResponse:
        # Determine display name
        given = payload.name.givenName if payload.name and payload.name.givenName else ""
        family = payload.name.familyName if payload.name and payload.name.familyName else ""
        display_name = (given + " " + family).strip() or payload.userName

        async with self.conn.transaction():
            # 1. Check if user exists globally by email
            existing_user = await self._get_user_by_email(payload.userName)

            if existing_user:
                user_id = existing_user["user_id"]

                # Ensure they are added to this tenant if not already
                # (You might want a check here to avoid unique constraint errors if they are already in the tenant)
                # For SCIM, we usually update the user if they exist, but here we just ensure ID resolution.
                # If we need to add them to the tenant:
                # await self.user_repo.add_user_to_tenant(...) # Logic to be added if cross-tenant invite logic applies here

                # For now, we assume if user exists, we just update the SCIM mapping or proceed.
                # However, if the user exists but is NOT in this tenant, we likely need to add them.
                # The generic create_user creates both User and UserTenant.
                # If you want to handle "Add existing user to tenant", that requires a separate Repo method.
                # Assuming for this fix we focus on creation or mapping update.
                pass
            else:
                # 2. Create new user
                # We manually construct the dict for UserRepository.create_user
                # because it expects 'hashed_password' and 'tenant_id'.
                random_pw = str(uuid4())
                hashed_pw = get_password_hash(random_pw)

                user_payload = {
                    "email": payload.userName,
                    "display_name": display_name,
                    "hashed_password": hashed_pw,
                    "tenant_id": str(tenant_id),
                    "tenant_role": "member",
                    "status": "active" if payload.active else "deactivated"
                }

                created_data = await self.user_repo.create_user(user_payload)
                # created_data is a dict: {'user': {...}, 'membership': {...}}
                user_id = created_data["user"]["user_id"]

            # 3. Create/Update SCIM Mapping
            external_id = payload.externalId or payload.userName
            await self.conn.execute(
                """
                INSERT INTO scim_mappings (tenant_id, user_id, external_id, active)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (tenant_id, external_id) 
                DO UPDATE SET user_id = EXCLUDED.user_id, active = EXCLUDED.active, created_at = now()
                """,
                tenant_id,
                user_id,
                external_id,
                payload.active
            )

            # Fetch created/updated timestamp for meta
            row = await self.conn.fetchrow(
                "SELECT created_at FROM users WHERE user_id = $1",
                user_id
            )
            created_at = row["created_at"]

        # 4. Build Response
        location = f"{base_url.rstrip('/')}/scim/v2/Users/{user_id}"
        meta = SCIMMeta(
            created=created_at,
            lastModified=created_at,
            location=location,
        )

        emails = payload.emails or [SCIMEmail(value=payload.userName, primary=True)]

        return SCIMUserResponse(
            id=user_id,
            userName=payload.userName,
            name=payload.name,
            emails=emails,
            active=payload.active,
            externalId=payload.externalId,
            meta=meta,
        )

    async def _get_user_by_email(self, email: str):
        return await self.conn.fetchrow(
            "SELECT user_id, primary_email FROM users WHERE primary_email = lower($1)",
            email,
        )