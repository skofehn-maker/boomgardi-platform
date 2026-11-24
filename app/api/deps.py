"""Reusable FastAPI dependencies (current user, role guards)."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


def _credentials_exception(detail: str = "اعتبارنامه نامعتبر است") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer`` header."""
    if credentials is None or not credentials.credentials:
        raise _credentials_exception("توکن دسترسی ارسال نشده است")

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
    except JWTError:
        raise _credentials_exception("توکن دسترسی نامعتبر یا منقضی شده است") from None

    if not subject:
        raise _credentials_exception()

    try:
        user_id = uuid.UUID(str(subject))
    except ValueError:
        raise _credentials_exception() from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_exception("حساب کاربری یافت نشد یا غیرفعال است")

    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Allow only users whose stored role is ``admin``."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این بخش فقط برای مدیران سامانه در دسترس است",
        )
    return user
