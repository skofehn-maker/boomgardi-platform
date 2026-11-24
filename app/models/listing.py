"""Listing and room models (Phase 2).

Datetimes are stored in UTC; conversion to Asia/Tehran happens only in the
presentation layer (browser-side formatting).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

LISTING_STATUSES = ("draft", "published", "archived")


class Listing(Base):
    """An eco-lodge accommodation owned by exactly one host user."""

    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("host_id", "idempotency_key", name="uq_listings_host_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    address: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)

    # Iron Rule 4: every mutating endpoint needs an Idempotency-Key. Storing it on
    # the listing lets a retry from the same host return the original row instead of
    # creating a duplicate (see ADR 0002).
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    rooms: Mapped[list["Room"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Listing id={self.id} title={self.title!r} status={self.status!r}>"


class Room(Base):
    """A bookable room inside a listing."""

    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    capacity: Mapped[int] = mapped_column(Integer)
    price_per_night: Mapped[float] = mapped_column(Float)

    listing: Mapped[Listing] = relationship(back_populates="rooms", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Room id={self.id} name={self.name!r} capacity={self.capacity}>"
