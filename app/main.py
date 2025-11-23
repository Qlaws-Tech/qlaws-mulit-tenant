from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
import logging

# --- Core Infrastructure ---
from app.core.database import db
from app.core.limiter import limiter
from app.core.cache import cache

# --- Feature Modules ---
from app.modules.tenants.router import router as tenant_router
from app.modules.users.router import router as user_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.mfa.router import router as mfa_router
from app.modules.roles.router import router as roles_router
from app.modules.groups.router import router as groups_router
from app.modules.audit.router import router as audit_router
from app.modules.sso.router import router as sso_router
from app.modules.api_keys.router import router as apikeys_router
from app.modules.scim.router import router as scim_router
from app.modules.system.router import router as system_router

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifecycle Manager.
    1. Connects to DB.
    2. VALIDATES HEALTH (Fail Fast).
    3. Serving Requests.
    4. Graceful Shutdown.
    """
    # 1. Startup: Connect DB
    logger.info("Connecting to Database...")
    await db.connect()

    # 2. Health Checks (Fail Fast)
    logger.info("Performing Startup Health Checks...")

    if not await db.ping():
        logger.critical("CRITICAL: Database is unreachable! Aborting startup.")
        raise RuntimeError("Database Health Check Failed")

    if not await cache.ping():
        logger.critical("CRITICAL: Redis is unreachable! Aborting startup.")
        raise RuntimeError("Redis Health Check Failed")

    logger.info("✅ System Healthy. Application starting.")

    yield

    # 3. Shutdown
    logger.info("Shutting down...")
    await db.disconnect()


app = FastAPI(
    title="QLaws Enterprise Backend",
    description="Multi-Tenant Identity & Access Management System (SOC 2 Ready)",
    version="1.0.0",
    lifespan=lifespan
)

# --- Rate Limiting Setup ---
app.state.limiter = limiter  # type: ignore


# Custom Handler for 429 Errors (Fixes type checking issues)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Handles 429 Too Many Requests errors from slowapi.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "type": "rate_limit_exceeded"
        }
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# --- Global Exception Handling ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to prevent stack trace leakage in production.
    """
    # In prod, log 'exc' to Sentry/Datadog here
    logger.error(f"Global Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
    )


# --- Router Registration ---
app.include_router(tenant_router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(mfa_router, prefix="/api/v1/auth/mfa", tags=["MFA"])
app.include_router(roles_router, prefix="/api/v1/roles", tags=["Roles"])
app.include_router(groups_router, prefix="/api/v1/groups", tags=["Groups"])
app.include_router(sso_router, prefix="/api/v1/sso", tags=["SSO"])
app.include_router(apikeys_router, prefix="/api/v1/api-keys", tags=["API Keys"])
app.include_router(scim_router, prefix="/scim/v2", tags=["SCIM"])
app.include_router(audit_router, prefix="/api/v1/audit", tags=["Audit"])
app.include_router(system_router, prefix="/api/v1/system", tags=["System"])


# --- Health Check (Runtime Liveness) ---
@app.get("/health", tags=["System"])
async def health_check():
    """
    Runtime probe for Load Balancers.
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
                "redis": "connected" if cache_health else "disconnected"
            }
        }
    )