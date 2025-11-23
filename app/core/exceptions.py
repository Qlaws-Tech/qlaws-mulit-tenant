from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse


# 1. Base Exception
class QLawsException(Exception):
    """Base class for all application-specific exceptions"""
    pass


# 2. Specific Domain Exceptions
class DuplicateDomainError(QLawsException):
    """Raised when a tenant tries to register a domain that already exists"""
    pass


class ResourceNotFound(QLawsException):
    """Generic 404 wrapper"""
    pass


# 3. The Exception Handler (Connects Logic to HTTP)
async def qlaws_exception_handler(request: Request, exc: QLawsException):
    if isinstance(exc, DuplicateDomainError):
        return JSONResponse(
            status_code=409,  # Conflict
            content={"detail": str(exc), "error_code": "DOMAIN_EXISTS"}
        )

    if isinstance(exc, ResourceNotFound):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "error_code": "NOT_FOUND"}
        )

    # Default catch-all for custom exceptions
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_code": "BAD_REQUEST"}
    )


# Helper to register them in main.py
def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(QLawsException, qlaws_exception_handler)