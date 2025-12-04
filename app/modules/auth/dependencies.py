from fastapi import Header, HTTPException

async def get_bearer_token(authorization: str = Header(None)) -> str:
    """
    Extract raw JWT token from Authorization header.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    return authorization.split(" ", 1)[1]
