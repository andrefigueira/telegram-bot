"""JWT authentication for the API."""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()


class TokenData(BaseModel):
    """JWT token payload."""
    tenant_id: str
    email: str
    exp: datetime


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def create_access_token(tenant_id: str, email: str) -> TokenResponse:
    """Create a JWT access token."""
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "tenant_id": tenant_id,
        "email": email,
        "exp": expires_at,
        "iat": datetime.utcnow()
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600
    )


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenData(
            tenant_id=payload["tenant_id"],
            email=payload["email"],
            exp=datetime.fromtimestamp(payload["exp"])
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """Get the current authenticated tenant from JWT token."""
    token = credentials.credentials
    return decode_token(token)


def get_tenant_id(token_data: TokenData = Depends(get_current_tenant)) -> str:
    """Get just the tenant ID from the token."""
    return token_data.tenant_id
