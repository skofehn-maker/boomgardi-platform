"""Booking endpoints.

``POST /api/v1/bookings`` reserves a room for the authenticated guest. Overlapping
stays of the same room are refused; the production-grade guarantee (PostgreSQL
``EXCLUDE USING gist``) is recorded in ADR 0005.
"""

from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.booking import Booking
from app.models.listing import Listing, Room
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse

router = APIRouter()

# Only these states hold a room; cancelled bookings release their dates.
BLOCKING_STATUSES = ("pending", "confirmed")


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a room for a date range",
)
async def create_booking(
    payload: BookingCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per booking attempt; a replay returns the original booking.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    if payload.check_out <= payload.check_in:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="تاریخ خروج باید بعد از تاریخ ورود باشد",
        )
    if payload.check_in < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="تاریخ ورود نمی‌تواند در گذشته باشد",
        )

    existing = await db.scalar(
        select(Booking).where(
            Booking.guest_id == current_user.id,
            Booking.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    room = await db.get(Room, payload.room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="اتاق یافت نشد"
        )

    listing = await db.get(Listing, room.listing_id)
    if listing is None or listing.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="این اتاق برای رزرو در دسترس نیست",
        )

    conflict = await db.scalar(
        select(Booking.id)
        .where(
            Booking.room_id == room.id,
            Booking.status.in_(BLOCKING_STATUSES),
            Booking.check_in < payload.check_out,
            Booking.check_out > payload.check_in,
        )
        .limit(1)
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این اتاق در بازه انتخاب‌شده قبلاً رزرو شده است",
        )

    booking = Booking(
        room_id=room.id,
        guest_id=current_user.id,
        check_in=payload.check_in,
        check_out=payload.check_out,
        status="pending",
        idempotency_key=idempotency_key,
    )
    db.add(booking)

    try:
        await db.commit()
    except IntegrityError:
        # Same key won a race: hand back the booking it created.
        await db.rollback()
        duplicate = await db.scalar(
            select(Booking).where(
                Booking.guest_id == current_user.id,
                Booking.idempotency_key == idempotency_key,
            )
        )
        if duplicate is None:
            raise
        return duplicate

    await db.refresh(booking)
    return booking
