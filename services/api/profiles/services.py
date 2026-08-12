from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB, Query

from services.api.profiles.models import ProfileCreate, ProfileUpdate, ProfileOut

_ROOT_DIR = Path(__file__).resolve().parents[3]
_PROFILES_DB_PATH = _ROOT_DIR / "data" / "profiles_db.json"


def _get_db_path() -> Path:
    """Ensure the data directory exists and return the DB path."""
    _PROFILES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DB_PATH


def _open_profiles_table():
    db = TinyDB(str(_get_db_path()))
    return db, db.table("profiles")


def _serialize_profile(doc) -> dict:
    """Convert a TinyDB document into a safe response dict."""
    return {
        "id": doc.doc_id,
        "user_id": doc["user_id"],
        "name": doc.get("name"),
        "phone": doc.get("phone"),
        "address": doc.get("address"),
    }


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def get_profile_by_user_id(user_id: int) -> dict | None:
    """Return the profile linked to the given user_id, or None."""
    db, table = _open_profiles_table()
    try:
        ProfileQuery = Query()
        results = table.search(ProfileQuery.user_id == user_id)
        if not results:
            return None
        return _serialize_profile(results[0])
    finally:
        db.close()


def create_profile(user_id: int, payload: ProfileCreate) -> dict:
    """Create a new profile for a user.

    Raises ValueError if a profile already exists for this user.
    """
    db, table = _open_profiles_table()
    try:
        ProfileQuery = Query()
        existing = table.search(ProfileQuery.user_id == user_id)
        if existing:
            raise ValueError(f"Profile already exists for user {user_id}.")

        doc_data = {
            "user_id": user_id,
            "name": payload.name,
            "phone": payload.phone,
            "address": payload.address,
        }

        doc_id = table.insert(doc_data)
        created = table.get(doc_id=doc_id)
        return _serialize_profile(created)
    finally:
        db.close()


def update_profile(user_id: int, payload: ProfileUpdate) -> dict | None:
    """Update profile fields for the given user.

    Returns the updated profile or None if no profile exists.
    """
    db, table = _open_profiles_table()
    try:
        ProfileQuery = Query()
        results = table.search(ProfileQuery.user_id == user_id)
        if not results:
            return None

        doc = results[0]
        update_data: dict = {}

        if payload.name is not None:
            update_data["name"] = payload.name
        if payload.phone is not None:
            update_data["phone"] = payload.phone
        if payload.address is not None:
            update_data["address"] = payload.address

        if update_data:
            table.update(update_data, doc_ids=[doc.doc_id])

        updated = table.get(doc_id=doc.doc_id)
        return _serialize_profile(updated)
    finally:
        db.close()
