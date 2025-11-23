from fastapi import APIRouter, Depends, HTTPException, Header
from app.dependencies.database import get_db_connection
from config_dev import settings
from app.modules.system.service import SystemService
from app.modules.system.repository import SystemRepository
from app.modules.system.schemas import CleanupResult

router = APIRouter()


# Define a new dependency for System Admin Auth
async def verify_system_key(x_system_key: str = Header(...)):
    # In production, add SYSTEM_KEY to settings.py
    # For this example, we hardcode or check against a setting
    SYSTEM_KEY = getattr(settings, "SYSTEM_KEY", "sys_admin_secret_123")

    if x_system_key != SYSTEM_KEY:
        raise HTTPException(status_code=403, detail="Invalid System Key")


async def get_system_service(conn=Depends(get_db_connection)):
    # Raw connection (Global operations)
    return SystemService(SystemRepository(conn))


@router.post("/cleanup", response_model=CleanupResult, dependencies=[Depends(verify_system_key)])
async def trigger_cleanup(service: SystemService = Depends(get_system_service)):
    """
    Trigger nightly maintenance tasks.
    Protected by 'X-System-Key'.
    """
    return await service.run_nightly_cleanup()