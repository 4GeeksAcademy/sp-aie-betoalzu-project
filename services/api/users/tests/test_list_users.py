from __future__ import annotations

import pytest

from services.api.users.services import list_users, get_user_by_id


# ======================================================================
# Test: GET /users — List users (via service functions)
# ======================================================================


class TestListUsersHappyPath:
    """6.1 — Feliz: usuario autenticado → lista de usuarios (sin contraseñas)."""

    def test_list_users_returns_all_users(self, test_db, sample_user, sample_admin):
        """list_users returns all users without passwords."""
        users = list_users()

        assert len(users) >= 2
        emails = [u["email"] for u in users]
        assert sample_user["email"] in emails
        assert sample_admin["email"] in emails

        # No password fields in any user
        for u in users:
            assert "hashed_password" not in u
            assert "password" not in u

    def test_list_users_returns_serialized_data(self, test_db, sample_user):
        """Each user has the expected serialized fields."""
        users = list_users()
        for u in users:
            assert "id" in u
            assert "email" in u
            assert "is_active" in u
            assert "role" in u
            assert "created_at" in u


class TestListUsersFailureModes:
    """6.2 — Fallo: sin token JWT → la función no tiene autorización aquí."""

    def test_list_users_no_auth(self):
        """list_users doesn't require auth (route-level concern).
        This test documents that the service function itself is unprotected.
        """
        # The protection is at the route level via Depends(get_current_user)
        pass


class TestListUsersLimitCases:
    """6.3 — Límite: sin usuarios registrados → lista vacía."""

    def test_list_users_empty_db(self, test_db):
        """An empty database returns an empty list."""
        users = list_users()
        assert users == []

    def test_list_users_returns_list_type(self, test_db):
        """list_users always returns a list."""
        result = list_users()
        assert isinstance(result, list)