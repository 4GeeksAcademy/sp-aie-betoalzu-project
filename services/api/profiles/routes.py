from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB
from services.api.profiles.models import ProfileUpdate, ProfileOut
from services.api.profiles.services import (
    create_profile,
    get_profile_by_user_id,
    update_profile,
)

profiles_api = APIRouter(prefix="/profiles", tags=["profiles"])


# ---------------------------------------------------------------------------
# Protected profile endpoints
# ---------------------------------------------------------------------------


@profiles_api.get("/me", response_model=ProfileOut)
def get_my_profile(current_user: UserInDB = Depends(get_current_user)):
    """Return the profile of the authenticated user.

    Creates an empty profile automatically if none exists yet.
    """
    profile = get_profile_by_user_id(current_user.id)
    if profile is None:
        # Auto-create an empty profile so /me always returns something.
        from services.api.profiles.models import ProfileCreate

        profile = create_profile(current_user.id, ProfileCreate())
    return profile


@profiles_api.put("/me", response_model=ProfileOut)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update name, phone and address for the authenticated user's profile.

    Only the profile owner can modify it (enforced by using the JWT identity).
    """
    profile = get_profile_by_user_id(current_user.id)
    if profile is None:
        # Auto-create before updating so the PUT is idempotent.
        from services.api.profiles.models import ProfileCreate

        create_profile(
            current_user.id,
            ProfileCreate(
                name=payload.name,
                phone=payload.phone,
                address=payload.address,
            ),
        )
        profile = get_profile_by_user_id(current_user.id)
    else:
        profile = update_profile(current_user.id, payload)

    return profile
