"""In-app notification endpoints (phase 14).

Every query is scoped by the authenticated user's id, so a caller can never read
or clear another account's notices. ``PATCH /read`` is an absolute
"unread -> read" write and therefore needs no dedup table (ADR 0012).
"""

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import MarkReadResponse, NotificationResponse

router = APIRouter()


@router.get(
    "/unread",
    response_model=list[NotificationResponse],
    summary="The current user's unread notifications",
)
async def list_unread(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="The current user's latest notifications",
)
async def list_latest(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.patch(
    "/read",
    response_model=MarkReadResponse,
    summary="Mark the current user's notifications as read",
)
async def mark_all_read(
    _idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Required on every mutation; replaying it is a no-op.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MarkReadResponse:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return MarkReadResponse(updated=result.rowcount or 0)
