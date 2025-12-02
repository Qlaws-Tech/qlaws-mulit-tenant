# app/modules/system/router.py

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.dependencies.database import get_db_connection
from app.modules.system.service import SystemService
from app.modules.system.schemas import CleanupResult

router = APIRouter(
    prefix="/system",
    tags=["System"],
)


def get_system_service(conn=Depends(get_db_connection)) -> SystemService:
    """
    Uses the system-level DB connection (no tenant RLS context),
    as this endpoint is meant for global maintenance.
    """
    return SystemService(conn)


@router.post(
    "/cleanup",
    response_model=CleanupResult,
)
async def run_cleanup(
    x_system_key: str = Header(None, alias="X-System-Key"),
    service: SystemService = Depends(get_system_service),
):
    """
    System maintenance endpoint.

    - Protected by a simple header: X-System-Key.
    - In tests, this is set to 'sys_admin_secret_123'.
    - Deletes expired refresh tokens, password reset tokens, and blacklist entries.
    """
    if x_system_key != "sys_admin_secret_123":
        # You can later move this constant into config/settings.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid system key",
        )

    result = await service.run_cleanup()
    return result
