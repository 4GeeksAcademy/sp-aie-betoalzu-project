from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from services.api.users.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.api.users.models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserUpdate,
    UserInDB,
)
from services.api.users.services import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    update_user,
    get_user_by_email,
    store_reset_token,
    validate_reset_token,
    invalidate_reset_token,
    update_user_password,
)

users_api = APIRouter()


def _json_error(message: str, status_code: int):
    return JSONResponse(content={"error": message}, status_code=status_code)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@users_api.post("/login")
def login(email: str, password: str):
    """Authenticate a user and return a JWT access token."""
    user = get_user_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Password reset / change
# ---------------------------------------------------------------------------


def _hash_token(token: str) -> str:
    """One-way hash of a token for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_reset_token() -> str:
    """Generate a cryptographically random reset token."""
    return os.urandom(32).hex()


RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30"))

# Email sender configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@nexova.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _send_reset_email(to_email: str, token: str) -> None:
    """Send a password-reset email via the Resend API.

    If RESEND_API_KEY is not configured, the email is silently skipped
    (useful during development).
    """
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"

    if not RESEND_API_KEY:
        print(f"[DEV] Password reset email to {to_email}: {reset_link}")
        return

    import requests  # lazy import

    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": "Restablece tu contrasena en Nexova",
                "html": f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f7fb;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f7fb;padding:24px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;">
<tr><td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px 24px;text-align:center;">
<h1 style="margin:0;font-size:22px;color:#ffffff;font-weight:700;">Nexova</h1>
<p style="margin:6px 0 0;font-size:14px;color:#c7d2fe;">Restablecimiento de contrasena</p>
</td></tr>
<tr><td style="padding:32px 24px;">
<h2 style="margin:0 0 8px;font-size:18px;color:#1e293b;">Hola,</h2>
<p style="margin:0 0 16px;font-size:14px;color:#475569;line-height:1.6;">
Recibiste este correo porque solicitaste restablecer tu contrasena en Nexova.
Haz clic en el boton de abajo para elegir una nueva contrasena.
</p>
<table cellpadding="0" cellspacing="0" style="margin:24px auto;">
<tr><td style="border-radius:999px;background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:12px 32px;">
<a href="{reset_link}" style="color:#ffffff;font-size:15px;font-weight:700;text-decoration:none;display:inline-block;">
Restablecer contrasena
</a>
</td></tr>
</table>
<p style="margin:16px 0 0;font-size:12px;color:#94a3b8;line-height:1.5;">
Si no solicitaste este cambio, puedes ignorar este correo. El enlace expira en {RESET_TOKEN_EXPIRE_MINUTES} minutos.
</p>
</td></tr>
<tr><td style="background-color:#f8fafc;padding:16px 24px;text-align:center;">
<p style="margin:0;font-size:12px;color:#94a3b8;">&copy; 2026 Nexova. Todos los derechos reservados.</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>""",
            },
            timeout=15,
        )
    except Exception as exc:
        print(f"[WARN] Failed to send reset email to {to_email}: {exc}")


@users_api.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    """Request a password reset token.

    Always returns 200 to prevent email enumeration.
    """
    user = get_user_by_email(payload.email)
    if user is not None:
        # Generate token, hash it for storage, and persist
        token = _generate_reset_token()
        token_hash = _hash_token(token)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        ).isoformat()
        store_reset_token(payload.email, token_hash, expires_at)
        _send_reset_email(payload.email, token)

    # Always return 200 — never reveal whether the email exists
    return {
        "message": "Si esa direccion de correo esta registrada, recibiras un enlace para restablecer tu contrasena en breve."
    }


@users_api.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """Reset a password using a valid token."""
    # We need the email — decode it from the token store.
    # We hash the incoming token and search for matching entries.
    token_hash = _hash_token(payload.token)

    # To find the email, search the reset_tokens table
    from tinydb import TinyDB, Query
    from pathlib import Path

    db_path = Path(__file__).resolve().parents[3] / "data" / "users_db.json"
    db = TinyDB(str(db_path))
    try:
        table = db.table("reset_tokens")
        TokenQuery = Query()
        results = table.search(
            (TokenQuery.token_hash == token_hash) & (TokenQuery.used == False)
        )
        if not results:
            return _json_error("Token invalido o ya utilizado.", 400)

        doc = results[0]
        expires_at = datetime.fromisoformat(doc["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            return _json_error("El token ha expirado.", 400)

        email = doc["email"]

        # Validate and update password
        if not validate_reset_token(email, token_hash):
            return _json_error("Token invalido o ya utilizado.", 400)

        new_hashed = hash_password(payload.new_password)
        update_user_password(email, new_hashed)
        invalidate_reset_token(email, token_hash)

        return {"message": "Contrasena restablecida correctamente."}
    finally:
        db.close()


@users_api.post("/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Change the authenticated user's password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        return _json_error("La contrasena actual es incorrecta.", 400)

    new_hashed = hash_password(payload.new_password)
    update_user_password(current_user.email, new_hashed)

    return {"message": "Contrasena actualizada correctamente."}


# ---------------------------------------------------------------------------
# CRUD — Users
# ---------------------------------------------------------------------------


@users_api.post("/users", status_code=201)
def register_user(payload: UserCreate):
    """Register a new user.

    Hashes the password before saving. Accepts optional profile fields
    (name, phone, address) and creates the linked Profile in the same operation.
    """
    try:
        result = create_user(payload)
        return result
    except ValueError as exc:
        return _json_error(str(exc), 409)


@users_api.get("/users")
def get_all_users(current_user: UserInDB = Depends(get_current_user)):
    """List all users (protected)."""
    return list_users()


@users_api.get("/users/{user_id}")
def get_user(user_id: int, current_user: UserInDB = Depends(get_current_user)):
    """Get a user by ID (protected)."""
    user = get_user_by_id(user_id)
    if user is None:
        return _json_error("User not found.", 404)
    return user


@users_api.put("/users/{user_id}")
def update_user_endpoint(
    user_id: int,
    payload: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """Update a user's credential fields.

    Protected — only the user themselves or an admin can update.
    Only admins can change the `role` field.
    """
    # Authorization: only the user themself or an admin
    if current_user.role.value != "admin" and current_user.id != user_id:
        return _json_error("Not authorized to update this user.", 403)

    # Non-admin users cannot change their own role
    if current_user.role.value != "admin" and payload.role is not None:
        return _json_error("Only admins can change the role field.", 403)

    try:
        updated = update_user(user_id, payload)
        if updated is None:
            return _json_error("User not found.", 404)
        return updated
    except ValueError as exc:
        return _json_error(str(exc), 409)


@users_api.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: int,
    current_user: UserInDB = Depends(get_current_user),
):
    """Delete a user (protected).

    Only admins or the user themselves can delete.
    The linked profile is also removed (embedded in the user document).
    """
    if current_user.role.value != "admin" and current_user.id != user_id:
        return _json_error("Not authorized to delete this user.", 403)

    deleted = delete_user(user_id)
    if not deleted:
        return _json_error("User not found.", 404)
    return {"message": "User deleted successfully."}