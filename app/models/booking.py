"""Booking model (Phase 5).

``check_in`` / ``check_out`` are calendar dates, so no timezone conversion
applies to them; ``created_at`` is stored in UTC like every other timestamp
(Iron Rule 3). Overlap protection is described in ADR 0005.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.listing import Room
    from app.models.user import User

BOOKING_STATUSES = ("pending", "confirmed", "cancelled")


class Booking(Base):
    """One stay of one guest in one room."""

    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint(
            "guest_id", "idempotency_key", name="uq_bookings_guest_idempotency"
        ),
        # A stay must end after it starts. SQLite can enforce this, so it lives
        # on the model; the PostgreSQL exclusion constraint cannot be rendered
        # by SQLite and therefore lives in the migration (ADR 0011).
        CheckConstraint("check_out > check_in", name="ck_bookings_dates"),
        Index("ix_bookings_room_check_in", "room_id", "check_in"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    guest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Iron Rule 4: a replayed create returns this row instead of booking twice.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    room: Mapped["Room"] = relationship(back_populates="bookings", lazy="selectin")
    guest: Mapped["User"] = relationship(lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Booking id={self.id} room={self.room_id} "
            f"{self.check_in}->{self.check_out} status={self.status!r}>"
        )
