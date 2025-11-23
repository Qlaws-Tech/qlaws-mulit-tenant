from fastapi import APIRouter, Depends, status
from app.dependencies.database import get_db_connection
from app.modules.tenants.service import TenantService
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate, TenantOnboardingResponse
from app.modules.users.repository import UserRepository
from app.modules.roles.repository import RoleRepository

router = APIRouter()

async def get_tenant_service(conn = Depends(get_db_connection)):
    # We inject multiple repositories into the service
    return TenantService(
        TenantRepository(conn),
        UserRepository(conn),
        RoleRepository(conn)
    )

@router.post("/", response_model=TenantOnboardingResponse, status_code=status.HTTP_201_CREATED)
async def onboard_new_tenant(
    tenant_data: TenantCreate,
    service: TenantService = Depends(get_tenant_service)
):
    """
    Public Onboarding Endpoint.
    Creates a Tenant AND the initial Admin User.
    """
    return await service.onboard_tenant(tenant_data)