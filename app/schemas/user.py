from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    # Self-service sign-up picks one of the two public roles; admin stays seeded.
    full_name: str | None = Field(default=None, max_length=255)
    role: Literal["guest", "host"] = "guest"


class UserUpdate(BaseModel):
    """Self-service profile update: every field optional, at least one set."""

    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        """Store a trimmed name; a blank name clears it."""
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def _require_a_change(self) -> "UserUpdate":
        if self.full_name is None and self.password is None:
            raise ValueError("دست‌کم یکی از نام یا گذرواژه باید ارسال شود")
        return self


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Public representation of a user (never contains the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Token envelope; ``role`` lets the clients route the user after login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    user: UserResponse
