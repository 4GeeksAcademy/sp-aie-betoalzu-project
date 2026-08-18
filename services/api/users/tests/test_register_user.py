from __future__ import annotations

import bcrypt
import pytest
from pydantic import ValidationError

from services.api.users.models import UserCreate, Role
from services.api.users.services import create_user, get_user_by_id, list_users
from services.api.users.tests.conftest import make_user_create


# ======================================================================
# Test: POST /users — Register user (via service functions)
# ======================================================================


class TestRegisterUserHappyPath:
    """5.1 — Feliz: datos válidos → crea usuario, devuelve datos sin contraseña."""

    def test_register_user_creates_and_returns_safe_data(self, test_db):
        """Creating a valid user returns serialized data without password."""
        payload = make_user_create(
            email="newuser@example.com",
            password="securepass123",
            role=Role.USER,
        )
        result = create_user(payload)

        assert result["email"] == "newuser@example.com"
        assert result["role"] == Role.USER.value
        assert result["is_active"] is True
        assert "hashed_password" not in result
        assert "password" not in result
        assert isinstance(result["id"], int)

    def test_register_user_returns_201_created(self, test_db):
        """The service function creates a user and returns it."""
        payload = make_user_create(email="jane@example.com", password="janepass123")
        result = create_user(payload)
        assert result["email"] == "jane@example.com"
        assert result["id"] is not None

    def test_register_user_with_full_profile(self, test_db):
        """5.5 — Feliz: con perfil opcional (name, phone, address) → guarda perfil."""
        payload = make_user_create(
            email="profileuser@example.com",
            password="profilepass123",
            name="John Doe",
            phone="555-1234",
            address="456 Oak St",
        )
        result = create_user(payload)

        assert result["profile"] is not None
        assert result["profile"]["name"] == "John Doe"
        assert result["profile"]["phone"] == "555-1234"
        assert result["profile"]["address"] == "456 Oak St"


class TestRegisterUserLimitCases:
    """5.2 — Límite: email duplicado → ValueError."""

    def test_register_user_duplicate_email_raises_error(self, test_db, sample_user):
        """Creating a user with an existing email raises ValueError."""
        payload = make_user_create(
            email=sample_user["email"],
            password="anotherpass123",
        )
        with pytest.raises(ValueError, match="already exists"):
            create_user(payload)


class TestRegisterUserFailureModes:
    """5.3–5.4 — Fallo: contraseña corta, email inválido."""

    def test_register_user_short_password(self, test_db):
        """Password shorter than 6 characters should fail Pydantic validation."""
        with pytest.raises(ValidationError):
            UserCreate(email="short@example.com", password="12")

    def test_register_user_empty_password(self, test_db):
        """Empty password should fail."""
        with pytest.raises(ValidationError):
            UserCreate(email="empty@example.com", password="")

    def test_register_user_invalid_email_format(self, test_db):
        """Invalid email format should fail Pydantic validation."""
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="validpass123")

    def test_register_user_empty_email(self, test_db):
        """Empty email should fail."""
        with pytest.raises(ValidationError):
            UserCreate(email="", password="validpass123")