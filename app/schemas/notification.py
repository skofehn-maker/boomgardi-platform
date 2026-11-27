from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """A notification as the bell dropdown sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message: str
    is_read: bool
    created_at: datetime


class MarkReadResponse(BaseModel):
    updated: int
