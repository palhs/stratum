"""
JWT authentication dependency for the Stratum Reasoning Engine.

Uses Supabase-issued JWTs (HS256, audience="authenticated").
SUPABASE_JWT_SECRET must be set in the environment.

Usage:
    from reasoning.app.auth import require_auth
    ...
    @router.get("/protected")
    async def protected(payload: dict = Depends(require_auth)):
        ...
"""
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# auto_error=False: prevents FastAPI's default 403 on missing header.
# We raise 401 ourselves when cred is None, matching the spec.
_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency that validates a Supabase JWT and returns the decoded payload.

    Raises:
        401 — Authorization header missing or token is malformed / unrecognised.
        403 — Token is expired or has the wrong audience.
    """
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = os.environ["SUPABASE_JWT_SECRET"]

    try:
        payload = jwt.decode(
            cred.credentials,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token expired",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token audience",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
