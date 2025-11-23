import httpx
from jose import jwt
from fastapi import HTTPException, status
from config_dev import settings


class TokenVerifier:
    """
    Strategy class to handle token verification based on configuration.
    """

    @staticmethod
    async def verify(token: str):
        if settings.AUTH_MODE == "local":
            return TokenVerifier._verify_local(token)
        elif settings.AUTH_MODE == "external":
            return await TokenVerifier._verify_external(token)
        else:
            raise ValueError("Invalid AUTH_MODE configured")

    @staticmethod
    def _verify_local(token: str):
        """
        Verifies locally signed HS256 tokens.
        """
        try:
            return jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    async def _verify_external(token: str):
        """
        Verifies RS256 tokens from Auth0/Okta/Keycloak using JWKS.
        """
        jwks_url = f"https://{settings.AUTH_DOMAIN}/.well-known/jwks.json"

        try:
            # 1. Fetch JWKS (Public Keys)
            # Optimization: In prod, cache this response!
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                jwks = response.json()

            # 2. Get Key ID (kid) from Header
            unverified_header = jwt.get_unverified_header(token)
            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }

            if not rsa_key:
                raise Exception("Public key not found for token")

            # 3. Verify Signature
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=[settings.AUTH_ALGORITHM],
                audience=settings.AUTH_AUDIENCE,
                issuer=f"https://{settings.AUTH_DOMAIN}/"
            )

            # 4. Map External Claims to Internal Context
            # Auth0 stores user_id in 'sub', but Tenant ID usually in a custom claim
            # e.g. "https://qlaws.com/tid"

            # We normalize the payload to match what our app expects
            return {
                "sub": payload.get("sub"),
                "tid": payload.get("https://qlaws.com/tid") or payload.get("tid"),  # Fallback
                "jti": payload.get("jti")
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"External Auth Failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )