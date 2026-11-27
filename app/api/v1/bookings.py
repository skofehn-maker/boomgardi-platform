"""Booking endpoints.

``POST /api/v1/bookings`` reserves a room for the authenticated guest. Overlapping
stays of the same room are refused; the production-grade guarantee (PostgreSQL
``EXCLUDE USING gist``) is recorded in ADR 0005.
"""

from datetime import date

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.models.booking import Booking
from app.models.listing import Listing, Room
from app.models.notification import Notification
from app.models.user import User
from app.schemas.booking import (
    AdminBookingResponse,
    BookingCreate,
    BookingResponse,
    GuestBookingResponse,
    HostBookingResponse,
)

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


@router.get(
    "/all",
    response_model=list[AdminBookingResponse],
    summary="Every booking in the system (admin only)",
)
async def list_all_bookings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[AdminBookingResponse]:
    """System-wide booking list for the admin panel, newest stays first.

    Both parties are fetched in the same statement: the guest through
    ``bookings.guest_id`` and the host through ``listings.host_id``.
    """
    guest = aliased(User)
    host = aliased(User)

    rows = await db.execute(
        select(
            Booking,
            guest.full_name,
            guest.email,
            host.full_name,
            host.email,
            Listing.id,
            Listing.title,
            Room.name,
        )
        .join(Room, Room.id == Booking.room_id)
        .join(Listing, Listing.id == Room.listing_id)
        .join(guest, guest.id == Booking.guest_id)
        .join(host, host.id == Listing.host_id)
        .order_by(Booking.check_in.desc(), Booking.created_at.desc())
    )

    return [
        AdminBookingResponse(
            id=booking.id,
            room_id=booking.room_id,
            guest_id=booking.guest_id,
            guest_name=guest_name,
            guest_email=guest_email,
            host_name=host_name,
            host_email=host_email,
            listing_id=listing_id,
            listing_title=listing_title,
            room_name=room_name,
            check_in=booking.check_in,
            check_out=booking.check_out,
            status=booking.status,
            created_at=booking.created_at,
        )
        for (
            booking,
            guest_name,
            guest_email,
            host_name,
            host_email,
            listing_id,
            listing_title,
            room_name,
        ) in rows.all()
    ]


@router.get(
    "/host",
    response_model=list[HostBookingResponse],
    summary="Bookings of the listings the current user hosts",
)
async def list_host_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HostBookingResponse]:
    """Every booking made against a room in one of the caller's listings."""
    rows = await db.execute(
        select(
            Booking,
            User.full_name,
            User.email,
            Room.name,
            Listing.id,
            Listing.title,
        )
        .join(Room, Room.id == Booking.room_id)
        .join(Listing, Listing.id == Room.listing_id)
        .join(User, User.id == Booking.guest_id)
        .where(Listing.host_id == current_user.id)
        .order_by(Booking.check_in.desc(), Booking.created_at.desc())
    )

    return [
        HostBookingResponse(
            id=booking.id,
            room_id=booking.room_id,
            guest_id=booking.guest_id,
            check_in=booking.check_in,
            check_out=booking.check_out,
            status=booking.status,
            created_at=booking.created_at,
            guest_name=guest_name,
            guest_email=guest_email,
            room_name=room_name,
            listing_id=listing_id,
            listing_title=listing_title,
        )
        for booking, guest_name, guest_email, room_name, listing_id, listing_title in rows.all()
    ]


@router.get(
    "/mine",
    response_model=list[GuestBookingResponse],
    summary="Bookings made by the current user",
)
async def list_my_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[GuestBookingResponse]:
    rows = await db.execute(
        select(
            Booking,
            Room.name,
            Room.price_per_night,
            Listing.id,
            Listing.title,
            Listing.city,
        )
        .join(Room, Room.id == Booking.room_id)
        .join(Listing, Listing.id == Room.listing_id)
        .where(Booking.guest_id == current_user.id)
        .order_by(Booking.check_in.desc(), Booking.created_at.desc())
    )

    return [
        GuestBookingResponse(
            id=booking.id,
            room_id=booking.room_id,
            check_in=booking.check_in,
            check_out=booking.check_out,
            status=booking.status,
            created_at=booking.created_at,
            room_name=room_name,
            price_per_night=price_per_night,
            listing_id=listing_id,
            listing_title=listing_title,
            listing_city=listing_city,
        )
        for booking, room_name, price_per_night, listing_id, listing_title, listing_city in rows.all()
    ]


async def _listing_for(db: AsyncSession, booking: Booking) -> Listing | None:
    """The listing a booking belongs to (booking -> room -> listing)."""
    room = await db.get(Room, booking.room_id)
    if room is None:
        return None
    return await db.get(Listing, room.listing_id)


def _notify(db: AsyncSession, user_id: uuid.UUID, message: str) -> None:
    """Queue an in-app notification on the caller's transaction (ADR 0012)."""
    db.add(Notification(user_id=user_id, message=message))


async def _load_host_booking(
    db: AsyncSession, booking_id: uuid.UUID, current_user: User
) -> Booking:
    """Fetch a booking and make sure the caller hosts the listing it belongs to."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="رزرو یافت نشد"
        )

    room = await db.get(Room, booking.room_id)
    listing = await db.get(Listing, room.listing_id) if room is not None else None
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="رزرو یافت نشد"
        )
    if listing.host_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این رزرو مربوط به اقامتگاه شما نیست",
        )

    return booking


async def _load_mutable_booking(
    db: AsyncSession, booking_id: uuid.UUID, current_user: User
) -> Booking:
    """Fetch a booking the caller may pay/cancel: its guest owner or hosting host."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="رزرو یافت نشد"
        )

    room = await db.get(Room, booking.room_id)
    listing = await db.get(Listing, room.listing_id) if room is not None else None
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="رزرو یافت نشد"
        )

    if booking.guest_id != current_user.id and listing.host_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این رزرو مربوط به شما نیست",
        )

    return booking


@router.patch(
    "/{booking_id}/confirm",
    response_model=BookingResponse,
    summary="Confirm a pending booking (host only)",
)
async def confirm_booking(
    booking_id: uuid.UUID,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per action; replaying it is a no-op.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = await _load_host_booking(db, booking_id, current_user)

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="رزرو لغوشده قابل تأیید نیست",
        )

    if booking.status != "confirmed":
        booking.status = "confirmed"
        listing = await _listing_for(db, booking)
        title = listing.title if listing is not None else "اقامتگاه"
        _notify(db, booking.guest_id, f"رزرو «{title}» تأیید شد.")
        await db.commit()
        await db.refresh(booking)

    return booking


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking (host only)",
)
async def cancel_booking(
    booking_id: uuid.UUID,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per action; replaying it is a no-op.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = await _load_mutable_booking(db, booking_id, current_user)

    if booking.status != "cancelled":
        booking.status = "cancelled"
        listing = await _listing_for(db, booking)
        title = listing.title if listing is not None else "اقامتگاه"

        # The actor already knows; tell the other party.
        if current_user.id == booking.guest_id:
            recipient = listing.host_id if listing is not None else booking.guest_id
        else:
            recipient = booking.guest_id
        _notify(db, recipient, f"رزرو «{title}» لغو شد.")

        await db.commit()
        await db.refresh(booking)

    return booking


@router.patch(
    "/{booking_id}/pay",
    response_model=BookingResponse,
    summary="Pay for a booking (mock: pending -> confirmed)",
)
async def pay_booking(
    booking_id: uuid.UUID,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Unique key per payment attempt; replaying it is a no-op.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = await _load_mutable_booking(db, booking_id, current_user)

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="رزرو لغوشده قابل پرداخت نیست",
        )

    if booking.status != "confirmed":
        booking.status = "confirmed"
        listing = await _listing_for(db, booking)
        title = listing.title if listing is not None else "اقامتگاه"
        _notify(
            db,
            booking.guest_id,
            f"پرداخت رزرو «{title}» انجام شد و رزرو تأیید شد.",
        )
        await db.commit()
        await db.refresh(booking)

    return booking
