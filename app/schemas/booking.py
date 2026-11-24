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
