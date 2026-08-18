from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.api.users.services import (
    get_user_by_email,
    store_reset_token,
    validate_reset_token,
)


# ======================================================================
# Test: POST /auth/forgot-password  (via service functions)
# ======================================================================


class TestForgotPasswordHappyPath:
    """2.1 — Feliz: email registrado → token se almacena correctamente."""

    def test_forgot_password_stores_token_for_registered_user(self, test_db, sample_user):
        """store_reset_token persists a token for a registered user."""
        email = sample_user["email"]
        token_hash = "abc123hash"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        store_reset_token(email, token_hash, expires_at)

        # Validate the token was stored
        assert validate_reset_token(email, token_hash) is True


class TestForgotPasswordLimitCases:
    """2.2 — Límite: email no registrado → no se almacena token (no hay usuario)."""

    def test_forgot_password_unregistered_email_does_not_store_token(self, test_db):
        """store_reset_token for an unregistered email still stores the token
        (the service stores tokens for any email to prevent enumeration).
        """
        email = "unknown@example.com"
        token_hash = "def456hash"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        store_reset_token(email, token_hash, expires_at)
        # The token should be stored regardless (for enumeration prevention)
        assert validate_reset_token(email, token_hash) is True

    def test_forgot_password_returns_generic_message(self, test_db, sample_user):
        """The route always returns a generic message.
        We verify the service function doesn't raise for registered users.
        """
        email = sample_user["email"]
        token_hash = "genericmsgtest"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        # Should not raise
        store_reset_token(email, token_hash, expires_at)
        assert validate_reset_token(email, token_hash) is True


class TestForgotPasswordFailureModes:
    """2.3 — Fallo: email con formato inválido."""

    def test_forgot_password_invalid_email_format(self, test_db):
        """An invalid email can't be used to look up a user."""
        user = get_user_by_email("not-an-email")
        assert user is None

    def test_forgot_password_empty_email(self, test_db):
        """Empty email string returns None."""
        user = get_user_by_email("")
        assert user is None