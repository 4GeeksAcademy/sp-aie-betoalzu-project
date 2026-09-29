from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
from tinydb import TinyDB, Query

from services.api.users.models import UserCreate, UserUpdate, UserInDB, UserOut, Role

_ROOT_DIR = Path(__file__).resolve().parents[3]
_USERS_DB_PATH = _ROOT_DIR / "data" / "users_db.json"


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db_path() -> Path:
    """Ensure the data directory exists and return the DB path."""
    _USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _USERS_DB_PATH


def _open_users_table():
    db = TinyDB(str(_get_db_path()))
    return db, db.table("users")


def _serialize_user(doc: dict) -> UserOut:
    """Convert a TinyDB document into a safe UserOut."""
    return UserOut(
        id=doc.doc_id,
        email=doc["email"],
        is_active=doc.get("is_active", True),
        role=Role(doc.get("role", Role.USER.value)),
        created_at=doc.get("created_at", ""),
        profile=doc.get("profile"),
    )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def create_user(payload: UserCreate) -> UserOut:
    """Create a user with hashed password + optional linked profile.

    Returns the serialized user (without password).
    """
    db, table = _open_users_table()
    try:
        UserQuery = Query()
        existing = table.search(UserQuery.email == payload.email)
        if existing:
            raise ValueError(f"User with email '{payload.email}' already exists.")

        hashed = bcrypt.hashpw(
            payload.password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
        profile_data = payload.profile.model_dump() if payload.profile else None

        doc_data: dict[str, Any] = {
            "email": payload.email,
            "hashed_password": hashed,
            "is_active": True,
            "role": payload.role.value,
            "created_at": _utc_now_str(),
            "profile": profile_data,
        }

        user_id = table.insert(doc_data)
        created = table.get(doc_id=user_id)
        return _serialize_user(created)
    finally:
        db.close()


def get_user_by_id(user_id: int) -> UserOut | None:
    """Return serialized user by doc id, or None."""
    db, table = _open_users_table()
    try:
        doc = table.get(doc_id=user_id)
        if doc is None:
            return None
        return _serialize_user(doc)
    finally:
        db.close()


def get_user_by_email(email: str) -> UserInDB | None:
    """Return full UserInDB (with hashed password) for auth, or None."""
    db, table = _open_users_table()
    try:
        UserQuery = Query()
        results = table.search(UserQuery.email == email)
        if not results:
            return None
        doc = results[0]
        return UserInDB(
            id=doc.doc_id,
            email=doc["email"],
            hashed_password=doc["hashed_password"],
            is_active=doc.get("is_active", True),
            role=Role(doc["role"]),
            created_at=doc.get("created_at", ""),
            profile=doc.get("profile"),
        )
    finally:
        db.close()


def list_users() -> list[UserOut]:
    """Return all users (serialized, no passwords)."""
    db, table = _open_users_table()
    try:
        return [_serialize_user(doc) for doc in table.all()]
    finally:
        db.close()


def update_user(user_id: int, payload: UserUpdate) -> UserOut | None:
    """Update credential / status fields.

    Returns the updated serialized user, or None if not found.
    """
    db, table = _open_users_table()
    try:
        doc = table.get(doc_id=user_id)
        if doc is None:
            return None

        update_data: dict[str, Any] = {}

        if payload.email is not None:
            UserQuery = Query()
            existing = table.search(UserQuery.email == payload.email)
            if existing and existing[0].doc_id != user_id:
                raise ValueError(f"Email '{payload.email}' is already in use.")
            update_data["email"] = payload.email

        if payload.password is not None:
            update_data["hashed_password"] = bcrypt.hashpw(
                payload.password.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")

        if payload.role is not None:
            update_data["role"] = payload.role.value

        if payload.is_active is not None:
            update_data["is_active"] = payload.is_active

        if payload.profile is not None:
            # Merge with existing profile instead of replacing entirely
            existing_profile = doc.get("profile") or {}
            existing_profile.update(payload.profile.model_dump(exclude_none=True))
            update_data["profile"] = existing_profile

        if update_data:
            table.update(update_data, doc_ids=[user_id])

        updated = table.get(doc_id=user_id)
        return _serialize_user(updated)
    finally:
        db.close()


def delete_user(user_id: int) -> bool:
    """Delete a user by doc id.

    Since the profile is embedded in the user document, deleting the user
    automatically removes the linked profile as well.
    Returns True if a document was removed.
    """
    db, table = _open_users_table()
    try:
        doc = table.get(doc_id=user_id)
        if doc is None:
            return False
        table.remove(doc_ids=[user_id])
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Password reset token helpers
# ---------------------------------------------------------------------------


def _open_reset_tokens_table():
    """Open the DB and return (db, reset_tokens_table)."""
    db = TinyDB(str(_get_db_path()))
    return db, db.table("reset_tokens")


def store_reset_token(email: str, token_hash: str, expires_at: str) -> None:
    """Persist a hashed reset token so we can validate + invalidate it later."""
    db, table = _open_reset_tokens_table()
    try:
        TokenQuery = Query()
        # Remove any previous tokens for this email (invalidate old ones)
        table.remove(TokenQuery.email == email)
        table.insert({
            "email": email,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "used": False,
        })
    finally:
        db.close()


def validate_reset_token(email: str, token_hash: str) -> bool:
    """Check whether a given token hash exists, is not expired and not used."""
    db, table = _open_reset_tokens_table()
    try:
        TokenQuery = Query()
        results = table.search(
            (TokenQuery.email == email)
            & (TokenQuery.token_hash == token_hash)
            & (TokenQuery.used == False)
        )
        if not results:
            return False
        doc = results[0]
        expires_at = datetime.fromisoformat(doc["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            return False
        return True
    finally:
        db.close()


def invalidate_reset_token(email: str, token_hash: str) -> None:
    """Mark a reset token as used so it cannot be reused."""
    db, table = _open_reset_tokens_table()
    try:
        TokenQuery = Query()
        table.update(
            {"used": True},
            (TokenQuery.email == email) & (TokenQuery.token_hash == token_hash),
        )
    finally:
        db.close()


def update_user_password(email: str, new_hashed_password: str) -> bool:
    """Update the hashed password for a user identified by email.

    Returns True if the user was found and updated.
    """
    db, table = _open_users_table()
    try:
        UserQuery = Query()
        results = table.search(UserQuery.email == email)
        if not results:
            return False
        doc = results[0]
        table.update({"hashed_password": new_hashed_password}, doc_ids=[doc.doc_id])
        return True
    finally:
        db.close()