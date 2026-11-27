"""In-app notification model (phase 14).

Rows are written in the same transaction as the booking status change they
describe (ADR 0012). ``created_at`` is UTC like every other timestamp (Iron
Rule 3); Jalali rendering happens in the browser.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    """One short message shown to one user in the navbar bell."""

    __tablename__ = "notifications"
    __table_args__ = (
        # The bell only ever asks "this user's unread rows", newest first.
        Index("ix_notifications_user_is_read", "user_id", "is_read"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    message: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Notification user={self.user_id} read={self.is_read}>"
