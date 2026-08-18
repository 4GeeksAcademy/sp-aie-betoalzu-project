from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Force test environment variables BEFORE any project imports
# ---------------------------------------------------------------------------
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["RESEND_API_KEY"] = ""
os.environ["FRONTEND_URL"] = "http://localhost:3000"

import importlib
import tempfile
from pathlib import Path
from typing import Any

import bcrypt
import pytest
from tinydb import TinyDB, Query

# Now import project modules (env vars must be set first)
import services.api.users.auth
importlib.reload(services.api.users.auth)

from services.api.users.models import UserCreate, Role
from services.api.users.auth import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Helper: create a temporary TinyDB and patch the service's DB path
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path() -> Path:
    """Create a temporary file path for the test database."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    yield path
    # Cleanup after test
    if path.exists():
        path.unlink()


@pytest.fixture
def test_db(tmp_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TinyDB:
    """Patch the services module to use a temporary DB and return the TinyDB instance."""

    # Patch _get_db_path() in services
    import services.api.users.services as svc

    original_get_db_path = svc._get_db_path

    def mock_get_db_path():
        tmp_db_path.parent.mkdir(parents=True, exist_ok=True)
        return tmp_db_path

    monkeypatch.setattr(svc, "_get_db_path", mock_get_db_path)

    # Also patch the reset-token helpers that call _get_db_path()
    # (they already call _get_db_path via _open_reset_tokens_table)

    # Patch _open_users_table and _open_reset_tokens_table to use the same path
    original_open_users = svc._open_users_table

    def mock_open_users():
        db = TinyDB(str(tmp_db_path))
        return db, db.table("users")

    monkeypatch.setattr(svc, "_open_users_table", mock_open_users)

    original_open_reset = svc._open_reset_tokens_table

    def mock_open_reset():
        db = TinyDB(str(tmp_db_path))
        return db, db.table("reset_tokens")

    monkeypatch.setattr(svc, "_open_reset_tokens_table", mock_open_reset)

    # Also patch the TinyDB usage in routes.py (reset-password endpoint)
    import services.api.users.routes as routes_mod
    # We'll patch the _hash_token and _generate_reset_token too if needed

    db = TinyDB(str(tmp_db_path))
    # Create tables
    db.table("users")
    db.table("reset_tokens")
    return db


# ---------------------------------------------------------------------------
# Sample user fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Return plain data for a sample user."""
    password = "testpass123"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return {
        "email": "alice@example.com",
        "hashed_password": hashed,
        "is_active": True,
        "role": Role.USER.value,
        "created_at": "2026-01-01T00:00:00+00:00",
        "profile": {"name": "Alice", "phone": "123456789", "address": "123 Main St"},
    }


@pytest.fixture
def sample_user(test_db: TinyDB, sample_user_data: dict[str, Any]) -> dict[str, Any]:
    """Insert a sample user into the test DB and return the doc."""
    table = test_db.table("users")
    doc_id = table.insert(sample_user_data)
    doc = table.get(doc_id=doc_id)
    doc["id"] = doc_id
    return doc


@pytest.fixture
def sample_admin_data() -> dict[str, Any]:
    """Return plain data for a sample admin user."""
    password = "adminpass123"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return {
        "email": "admin@example.com",
        "hashed_password": hashed,
        "is_active": True,
        "role": Role.ADMIN.value,
        "created_at": "2026-01-01T00:00:00+00:00",
        "profile": {"name": "Admin", "phone": "000000000", "address": "Admin Office"},
    }


@pytest.fixture
def sample_admin(test_db: TinyDB, sample_admin_data: dict[str, Any]) -> dict[str, Any]:
    """Insert a sample admin into the test DB and return the doc."""
    table = test_db.table("users")
    doc_id = table.insert(sample_admin_data)
    doc = table.get(doc_id=doc_id)
    doc["id"] = doc_id
    return doc


@pytest.fixture
def sample_inactive_user_data() -> dict[str, Any]:
    """Return data for an inactive user."""
    password = "inactivepass"
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return {
        "email": "inactive@example.com",
        "hashed_password": hashed,
        "is_active": False,
        "role": Role.USER.value,
        "created_at": "2026-01-01T00:00:00+00:00",
        "profile": None,
    }


@pytest.fixture
def sample_inactive_user(test_db: TinyDB, sample_inactive_user_data: dict[str, Any]) -> dict[str, Any]:
    """Insert an inactive user into the test DB."""
    table = test_db.table("users")
    doc_id = table.insert(sample_inactive_user_data)
    doc = table.get(doc_id=doc_id)
    doc["id"] = doc_id
    return doc


# ---------------------------------------------------------------------------
# Auth headers fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers(sample_user: dict[str, Any]) -> dict[str, str]:
    """Generate a JWT token for the sample user."""
    token = create_access_token(
        data={"sub": sample_user["email"], "role": sample_user["role"]}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(sample_admin: dict[str, Any]) -> dict[str, str]:
    """Generate a JWT token for the admin user."""
    token = create_access_token(
        data={"sub": sample_admin["email"], "role": sample_admin["role"]}
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helper to create a fully usable UserCreate payload
# ---------------------------------------------------------------------------

def make_user_create(
    email: str = "newuser@example.com",
    password: str = "securepass123",
    role: Role = Role.USER,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
) -> UserCreate:
    """Convenience factory for UserCreate."""
    from services.api.users.models import Profile
    profile = None
    if name or phone or address:
        profile = Profile(name=name, phone=phone, address=address)
    return UserCreate(email=email, password=password, role=role, profile=profile)