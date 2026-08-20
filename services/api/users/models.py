from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    
    @classmethod
    def _missing_(cls, value: object) -> Role | None:
        """Reject any value that is not one of the allowed roles."""
        raise ValueError(f"Invalid role '{value}'. Must be one of: {', '.join(r.value for r in cls)}")


class Profile(BaseModel):
    """Optional profile fields stored alongside the user."""
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: Role = Role.USER
    profile: Profile | None = None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6)
    role: Role | None = None
    is_active: bool | None = None
    profile: Profile | None = None


class UserOut(BaseModel):
    """Safe output representation — no password."""
    id: int
    email: str
    is_active: bool
    role: Role
    created_at: str
    profile: Profile | None = None


class UserInDB(BaseModel):
    """Internal representation with hashed_password."""
    id: int
    email: str
    hashed_password: str
    is_active: bool
    role: Role
    created_at: str
    profile: Profile | None = None


# ---------------------------------------------------------------------------
# Password reset models
# ---------------------------------------------------------------------------


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)