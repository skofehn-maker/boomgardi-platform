"""Password hashing and JWT helpers.

Expiry claims are timezone-aware UTC (Iron rule 3). Conversion to
``Asia/Tehran`` happens only in the presentation layer.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration (values come from .env through pydantic-settings)
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``False`` for malformed/unknown hashes instead of raising."""
    if not hashed_password:
        return False
    try:
        return password_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Build a signed HS256 access token.

    ``sub`` is normalised to a string because the JWT spec requires it and
    :class:`uuid.UUID` is not JSON serialisable.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode: dict[str, Any] = dict(data)
    to_encode.update({"iat": now, "exp": expire})
    if to_encode.get("sub") is not None:
        to_encode["sub"] = str(to_encode["sub"])

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a token; raises :class:`jose.JWTError` when invalid."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


__all__ = [
    "JWTError",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
