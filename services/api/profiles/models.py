from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProfileCreate(BaseModel):
    """Payload for creating a new profile."""
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    """Payload for updating profile fields (PUT)."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileOut(BaseModel):
    """Safe output representation of a profile."""
    id: int
    user_id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None
