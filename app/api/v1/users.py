from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[User]:
    """List every user, newest first. Admin only."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's name and/or password",
)
async def update_me(
    payload: UserUpdate,
    _idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description=(
            "Unique key per attempt; the writes are absolute, so a replay "
            "converges on the same state (ADR 0010)."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Update the caller's own profile.

    The subject always comes from the access token, so a request can never
    touch another account, and the password is only ever stored hashed.
    """
    changes = payload.model_dump(exclude_unset=True)

    if "full_name" in changes:
        current_user.full_name = changes["full_name"]
    if changes.get("password"):
        current_user.password_hash = hash_password(changes["password"])

    await db.commit()
    await db.refresh(current_user)
    return current_user
