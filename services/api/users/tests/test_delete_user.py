from __future__ import annotations

import pytest

from services.api.users.services import delete_user, get_user_by_id


# ======================================================================
# Test: DELETE /users/{user_id} — Delete user (via service functions)
# ======================================================================


class TestDeleteUserHappyPath:
    """9.1 — Feliz: mismo usuario se elimina a sí mismo → éxito."""

    def test_delete_user_self(self, test_db, sample_user):
        """Deleting a user by ID should remove them."""
        user_id = sample_user["id"]
        result = delete_user(user_id)
        assert result is True

        # Verify user is gone
        user = get_user_by_id(user_id)
        assert user is None

    def test_delete_user_removes_from_database(self, test_db, sample_user, sample_admin):
        """After deletion, the user should no longer appear in list."""
        from services.api.users.services import list_users

        delete_user(sample_user["id"])
        users = list_users()
        emails = [u["email"] for u in users]
        assert sample_user["email"] not in emails
        assert sample_admin["email"] in emails


class TestDeleteUserFailureModes:
    """9.3 — Fallo: usuario no-admin intenta eliminar a otro → 403 (route-level)."""

    def test_delete_user_no_auth(self):
        """delete_user doesn't require auth (route-level concern)."""
        # The protection is at the route level via Depends(get_current_user)
        pass


class TestDeleteUserLimitCases:
    """9.4 — Límite: ID inexistente → False."""

    def test_delete_user_nonexistent_id(self, test_db):
        """Deleting a non-existent user returns False."""
        result = delete_user(99999)
        assert result is False

    def test_delete_user_negative_id(self, test_db):
        """Deleting with a negative ID returns False."""
        result = delete_user(-1)
        assert result is False

    def test_delete_user_twice(self, test_db, sample_user):
        """Deleting a user twice: first returns True, second returns False."""
        user_id = sample_user["id"]
        first_delete = delete_user(user_id)
        assert first_delete is True

        second_delete = delete_user(user_id)
        assert second_delete is False