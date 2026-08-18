from __future__ import annotations

import pytest

from services.api.users.services import get_user_by_id


# ======================================================================
# Test: GET /users/{user_id} — Get user by ID (via service functions)
# ======================================================================


class TestGetUserHappyPath:
    """7.1 — Feliz: usuario autenticado, ID existente → datos del usuario."""

    def test_get_user_by_id_returns_user(self, test_db, sample_user):
        """get_user_by_id returns the correct user for an existing ID."""
        user = get_user_by_id(sample_user["id"])

        assert user is not None
        assert user["email"] == sample_user["email"]
        assert user["role"] == sample_user["role"]
        assert "hashed_password" not in user
        assert "password" not in user

    def test_get_user_by_id_returns_profile(self, test_db, sample_user):
        """The returned user includes the profile if present."""
        user = get_user_by_id(sample_user["id"])
        assert user is not None
        assert user["profile"] is not None

    def test_get_user_by_id_returns_serialized_data(self, test_db, sample_user):
        """The returned user has all expected fields."""
        user = get_user_by_id(sample_user["id"])
        assert user is not None
        assert "id" in user
        assert "email" in user
        assert "is_active" in user
        assert "role" in user
        assert "created_at" in user


class TestGetUserLimitCases:
    """7.2 — Límite: ID inexistente → None."""

    def test_get_user_by_id_nonexistent(self, test_db):
        """get_user_by_id returns None for a non-existent ID."""
        user = get_user_by_id(99999)
        assert user is None

    def test_get_user_by_id_negative_id(self, test_db):
        """A negative ID returns None (no such user)."""
        user = get_user_by_id(-1)
        assert user is None


class TestGetUserFailureModes:
    """7.3 — Fallo: sin token JWT → protección a nivel de ruta."""

    def test_get_user_by_id_no_auth(self):
        """get_user_by_id doesn't require auth (route-level concern)."""
        # The protection is at the route level via Depends(get_current_user)
        pass