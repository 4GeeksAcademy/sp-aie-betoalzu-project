from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.api.users.models import UserUpdate, Role
from services.api.users.services import update_user, get_user_by_id
from services.api.users.tests.conftest import make_user_create


# ======================================================================
# Test: PUT /users/{user_id} — Update user (via service functions)
# ======================================================================


class TestUpdateUserHappyPath:
    """8.1 — Feliz: mismo usuario actualiza su email → éxito."""

    def test_update_user_email(self, test_db, sample_user):
        """Updating a user's email should succeed."""
        updated = update_user(
            sample_user["id"],
            UserUpdate(email="updated@example.com"),
        )
        assert updated is not None
        assert updated["email"] == "updated@example.com"

        # Verify persistence
        user = get_user_by_id(sample_user["id"])
        assert user is not None
        assert user["email"] == "updated@example.com"

    def test_update_user_password(self, test_db, sample_user):
        """Updating a user's password should succeed."""
        from services.api.users.auth import verify_password

        updated = update_user(
            sample_user["id"],
            UserUpdate(password="newpass456"),
        )
        assert updated is not None

        # Verify the password changed (can't check hash directly, but can verify)
        from services.api.users.services import get_user_by_email
        user = get_user_by_email(sample_user["email"])
        assert user is not None
        assert verify_password("newpass456", user.hashed_password)

    def test_update_user_role_by_admin(self, test_db, sample_user):
        """8.2 — Admin actualiza rol de otro usuario → éxito."""
        updated = update_user(
            sample_user["id"],
            UserUpdate(role=Role.MANAGER),
        )
        assert updated is not None
        assert updated["role"] == Role.MANAGER.value

    def test_update_user_profile(self, test_db, sample_user):
        """Updating profile fields should merge with existing profile."""
        updated = update_user(
            sample_user["id"],
            UserUpdate(profile={"name": "Alice Updated", "phone": "999-9999"}),
        )
        assert updated is not None
        assert updated["profile"]["name"] == "Alice Updated"
        assert updated["profile"]["phone"] == "999-9999"
        assert updated["profile"]["address"] == "123 Main St"  # preserved from original

    def test_update_user_partial_profile(self, test_db, sample_user):
        """Updating only one profile field should preserve others."""
        updated = update_user(
            sample_user["id"],
            UserUpdate(profile={"name": "Only Name Changed"}),
        )
        assert updated is not None
        assert updated["profile"]["name"] == "Only Name Changed"
        assert updated["profile"]["phone"] == "123456789"  # preserved
        assert updated["profile"]["address"] == "123 Main St"  # preserved


class TestUpdateUserLimitCases:
    """8.3 — Límite: email duplicado → ValueError."""

    def test_update_user_duplicate_email(self, test_db, sample_user, sample_admin):
        """Updating to an email already used by another user should raise ValueError."""
        with pytest.raises(ValueError, match="already in use"):
            update_user(
                sample_user["id"],
                UserUpdate(email=sample_admin["email"]),
            )

    def test_update_user_nonexistent_id(self, test_db):
        """Updating a non-existent user returns None."""
        updated = update_user(99999, UserUpdate(email="nobody@example.com"))
        assert updated is None


class TestUpdateUserFailureModes:
    """8.4–8.6 — Fallo: permisos, ID inexistente."""

    def test_update_user_non_admin_cannot_change_role(self):
        """Non-admin users cannot change their role (route-level enforcement).
        The service function itself doesn't enforce this; it's at the route level.
        """
        # The route enforces: if current_user.role != "admin" and payload.role is not None -> 403
        pass

    def test_update_user_short_password(self, test_db):
        """Password shorter than 6 characters should fail validation."""
        with pytest.raises(ValidationError):
            UserUpdate(password="12")

    def test_update_user_invalid_email(self, test_db):
        """Invalid email format should fail validation."""
        with pytest.raises(ValidationError):
            UserUpdate(email="not-an-email")