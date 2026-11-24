from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    capacity: int = Field(ge=1, le=50)
    price_per_night: float = Field(gt=0)


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    listing_id: UUID
    name: str
    capacity: int
    price_per_night: float


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=3, max_length=255)


class ListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    host_id: UUID
    title: str
    description: str | None = None
    city: str
    address: str
    status: str
    created_at: datetime
    rooms: list[RoomResponse] = Field(default_factory=list)
