from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.api.users.services import (
    store_reset_token,
    validate_reset_token,
    invalidate_reset_token,
    update_user_password,
    get_user_by_email,
)
from services.api.users.auth import hash_password, verify_password


# ======================================================================
# Test: POST /auth/reset-password  (via service functions)
# ======================================================================


class TestResetPasswordHappyPath:
    """3.1 — Feliz: token válido y no expirado → actualiza contraseña, invalida token."""

    def test_reset_password_valid_token_updates_password(self, test_db, sample_user):
        """A valid, non-expired token should allow password update and then be invalidated."""
        email = sample_user["email"]
        token_hash = "validtokenhash123"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        new_password = "newsecurepass456"

        store_reset_token(email, token_hash, expires_at)

        # Validate the token
        assert validate_reset_token(email, token_hash) is True

        # Update the password
        new_hashed = hash_password(new_password)
        update_user_password(email, new_hashed)

        # Verify the new password works
        user = get_user_by_email(email)
        assert user is not None
        assert verify_password(new_password, user.hashed_password)

        # Invalidate the token
        invalidate_reset_token(email, token_hash)
        assert validate_reset_token(email, token_hash) is False


class TestResetPasswordLimitCases:
    """3.2 — Límite: token expirado → validate_reset_token returns False."""

    def test_reset_password_expired_token(self, test_db, sample_user):
        """An expired token should not be valid."""
        email = sample_user["email"]
        token_hash = "expiredtokenhash"
        expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

        store_reset_token(email, token_hash, expires_at)
        assert validate_reset_token(email, token_hash) is False


class TestResetPasswordFailureModes:
    """3.3–3.5 — Fallo: token usado, inexistente, contraseña corta."""

    def test_reset_password_used_token(self, test_db, sample_user):
        """A token that was already used should not be valid."""
        email = sample_user["email"]
        token_hash = "usedtokenhash"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        store_reset_token(email, token_hash, expires_at)
        # Use (invalidate) the token
        invalidate_reset_token(email, token_hash)
        assert validate_reset_token(email, token_hash) is False

    def test_reset_password_nonexistent_token(self, test_db, sample_user):
        """A random non-existent token should not be valid."""
        email = sample_user["email"]
        assert validate_reset_token(email, "randomnonexistenttoken") is False

    def test_reset_password_short_new_password(self, test_db, sample_user):
        """A new password shorter than 6 characters is invalid (Pydantic validation)."""
        from pydantic import ValidationError
        from services.api.users.models import ResetPasswordRequest

        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="sometoken", new_password="12")

    def test_reset_password_empty_new_password(self, test_db, sample_user):
        """An empty password should fail validation."""
        from pydantic import ValidationError
        from services.api.users.models import ResetPasswordRequest

        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="sometoken", new_password="")