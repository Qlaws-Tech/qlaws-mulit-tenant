from datetime import datetime, timedelta, timezone
from typing import Any, Union
from uuid import uuid4
from jose import jwt
from passlib.context import CryptContext
from config_dev import settings

# Setup Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if the typed password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password for storage."""
    return pwd_context.hash(password)


def create_access_token(subject: Union[str, Any], tenant_id: str) -> str:
    """
    Creates a JWT containing:
    - sub: User ID
    - tid: Tenant ID (Context)
    - jti: Unique Token ID (For revocation)
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Generate a unique identifier for this specific token
    jti = str(uuid4())

    to_encode = {
        "sub": str(subject),
        "tid": str(tenant_id),
        "exp": expire,
        "jti": jti  # Unique ID used for blacklisting
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt