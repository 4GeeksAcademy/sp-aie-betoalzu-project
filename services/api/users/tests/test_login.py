from __future__ import annotations

from unittest.mock import ANY

import bcrypt
import pytest
from tinydb import Query

from services.api.users.auth import verify_password, create_access_token
from services.api.users.services import get_user_by_email, list_users


# ======================================================================
# Test: POST /login  (via service functions + auth)
# ======================================================================


class TestLoginHappyPath:
    """1.1 — Feliz: credenciales correctas → devuelve access_token y token_type."""

    def test_login_success_returns_token(self, test_db, sample_user):
        """Verify that correct credentials generate a valid JWT."""
        email = sample_user["email"]
        password = "testpass123"

        user = get_user_by_email(email)
        assert user is not None
        assert verify_password(password, user.hashed_password)

        token = create_access_token(data={"sub": user.email, "role": user.role.value})
        assert token is not None
        assert isinstance(token, str)
        # The token should have two dots (three base64url segments)
        assert token.count(".") == 2


class TestLoginLimitCases:
    """1.2 — Límite: email no registrado → 401."""

    def test_login_unregistered_email_returns_none(self, test_db):
        """get_user_by_email returns None for unregistered emails."""
        user = get_user_by_email("nonexistent@example.com")
        assert user is None


class TestLoginFailureModes:
    """1.3 — Fallo: contraseña incorrecta → verify_password returns False."""

    def test_login_wrong_password(self, test_db, sample_user):
        """verify_password returns False for wrong password."""
        user = get_user_by_email(sample_user["email"])
        assert user is not None
        assert not verify_password("wrongpassword", user.hashed_password)

    def test_login_inactive_user(self, test_db, sample_inactive_user):
        """Inactive user can be retrieved but is_active is False."""
        user = get_user_by_email(sample_inactive_user["email"])
        assert user is not None
        assert user.is_active is False

    def test_login_empty_email_returns_none(self, test_db):
        """Empty email returns None (no user with empty email)."""
        user = get_user_by_email("")
        assert user is None

    def test_login_invalid_email_format_returns_none(self, test_db):
        """Malformed email returns None."""
        user = get_user_by_email("not-an-email")
        assert user is None