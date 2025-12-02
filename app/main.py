# app/main.py

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import db
from app.core.cache import cache

from app.dependencies.rls import tenant_context_middleware

# Routers
from app.modules.tenants.router import router as tenants_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.roles.router import router as roles_router
from app.modules.groups.router import router as groups_router
from app.modules.api_keys.router import router as api_keys_router
from app.modules.audit.router import router as audit_router
from app.modules.sso.router import router as sso_router
from app.modules.scim.router import router as scim_router
from app.modules.system.router import router as system_router
from app.modules.invitations.router import router as invitations_router
from app.modules.auth.mfa.router import router as mfa_router

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.
    - Connect DB pool
    - Connect Redis
    """
    logger.info("Starting QLAWS application...")
    await db.connect()
    await cache.connect()
    logger.info("Database and cache connections established.")
    yield
    logger.info("Shutting down QLAWS application...")
    await db.disconnect()
    await cache.close()
    logger.info("Database and cache connections closed.")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS (tighten allow_origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tenant context middleware (X-Tenant-ID + JWT tid)
app.middleware("http")(tenant_context_middleware)


# -------------------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """
    Runtime liveness probe used by infra / load balancers.
    Verifies DB and Redis.
    """
    db_health = await db.ping()
    cache_health = await cache.ping()

    status_code = 200 if (db_health and cache_health) else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "unhealthy",
            "components": {
                "database": "connected" if db_health else "disconnected",
                "redis": "connected" if cache_health else "disconnected",
            },
        },
    )


# -------------------------------------------------------------------
# API ROUTERS (versioned)
# -------------------------------------------------------------------
API_PREFIX = "/api/v1"

# Each router has its own internal prefix, e.g. "/tenants", "/auth", ...
app.include_router(tenants_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(roles_router, prefix=API_PREFIX)
app.include_router(groups_router, prefix=API_PREFIX)
app.include_router(api_keys_router, prefix=API_PREFIX)
app.include_router(audit_router, prefix=API_PREFIX)
app.include_router(sso_router, prefix=API_PREFIX)
app.include_router(system_router, prefix=API_PREFIX)
app.include_router(invitations_router, prefix=API_PREFIX)
app.include_router(mfa_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)

# -------------------------------------------------------------------
# SCIM ROUTER (NOT under /api/v1)
# -------------------------------------------------------------------
# SCIM spec uses /scim/v2/... and tests hit "/scim/v2/Users"
app.include_router(scim_router)


# -------------------------------------------------------------------
# Global middleware hook (optional logging/tracing)
# -------------------------------------------------------------------
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    # Placeholder for request logging / tracing
    response = await call_next(request)
    return response
