from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BookingCreate(BaseModel):
    room_id: UUID
    check_in: date
    check_out: date


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    guest_id: UUID
    check_in: date
    check_out: date
    status: str
    created_at: datetime


class HostBookingResponse(BookingResponse):
    """A booking as the host sees it: who, which room, which listing."""

    guest_name: str | None = None
    guest_email: str
    room_name: str
    listing_id: UUID
    listing_title: str


class AdminBookingResponse(BaseModel):
    """A booking as the admin panel sees it: guest, host, listing and dates."""

    id: UUID
    room_id: UUID
    guest_id: UUID
    guest_name: str | None = None
    guest_email: str
    host_name: str | None = None
    host_email: str
    listing_id: UUID
    listing_title: str
    room_name: str
    check_in: date
    check_out: date
    status: str
    created_at: datetime


class GuestBookingResponse(BaseModel):
    """A booking as the guest sees it: what was booked and where."""

    id: UUID
    room_id: UUID
    check_in: date
    check_out: date
    status: str
    created_at: datetime
    room_name: str
    price_per_night: float
    listing_id: UUID
    listing_title: str
    listing_city: str
