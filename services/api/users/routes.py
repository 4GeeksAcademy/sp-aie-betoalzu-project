from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from services.api.users.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from services.api.users.models import UserCreate, UserUpdate, UserInDB
from services.api.users.services import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    update_user,
    get_user_by_email,
)

users_api = APIRouter()


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@users_api.post("/login")
def login(email: str, password: str):
    """Authenticate a user and return a JWT access token."""
    user = get_user_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# CRUD — Users
# ---------------------------------------------------------------------------


@users_api.post("/users", status_code=201)
def register_user(payload: UserCreate):
    """Register a new user.

    Hashes the password before saving. Accepts optional profile fields
    (name, phone, address) and creates the linked Profile in the same operation.
    """
    try:
        result = create_user(payload)
        return result
    except ValueError as exc:
        return _json_error(str(exc), 409)


@users_api.get("/users")
def get_all_users(current_user: UserInDB = Depends(get_current_user)):
    """List all users (protected)."""
    return list_users()


@users_api.get("/users/{user_id}")
def get_user(user_id: int, current_user: UserInDB = Depends(get_current_user)):
    """Get a user by ID (protected)."""
    user = get_user_by_id(user_id)
    if user is None:
        return _json_error("User not found.", 404)
    return user


@users_api.put("/users/{user_id}")
def update_user_endpoint(
    user_id: int,
    payload: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update a user's credential fields.

    Protected — only the user themselves or an admin can update.
    Only admins can change the `role` field.
    """
    # Authorization: only the user themself or an admin
    if current_user.role.value != "admin" and current_user.id != user_id:
        return _json_error("Not authorized to update this user.", 403)

    # Non-admin users cannot change their own role
    if current_user.role.value != "admin" and payload.role is not None:
        return _json_error("Only admins can change the role field.", 403)

    try:
        updated = update_user(user_id, payload)
        if updated is None:
            return _json_error("User not found.", 404)
        return updated
    except ValueError as exc:
        return _json_error(str(exc), 409)


@users_api.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: int,
    current_user: UserInDB = Depends(get_current_user),
):
    """Delete a user (protected).

    Only admins or the user themselves can delete.
    The linked profile is also removed (embedded in the user document).
    """
    if current_user.role.value != "admin" and current_user.id != user_id:
        return _json_error("Not authorized to delete this user.", 403)

    deleted = delete_user(user_id)
    if not deleted:
        return _json_error("User not found.", 404)
    return {"message": "User deleted successfully."}