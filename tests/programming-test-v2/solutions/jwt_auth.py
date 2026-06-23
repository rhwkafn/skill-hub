"""
JWT Authentication Module

Provides user registration, login with bcrypt password hashing,
JWT token generation/verification, and a protected route decorator.
"""

import functools
import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ---------------------------------------------------------------------------
# In-memory user store (swap for a real DB in production)
# ---------------------------------------------------------------------------

_users: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Password hashing (bcrypt-like interface using stdlib)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations=100_000)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt_hex, dk_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        dk = bytes.fromhex(dk_hex)
        new_dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations=100_000)
        return hmac.compare_digest(dk, new_dk)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# JWT helpers (minimal implementation -- no external deps required)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return urlsafe_b64decode(s)


def _sign(message: str, secret: str) -> str:
    """Create HMAC-SHA256 signature and return base64url-encoded."""
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_token(
    payload: dict[str, Any],
    secret: str = SECRET_KEY,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT token.

    Args:
        payload: Claims to include in the token.
        secret: Signing secret.
        expires_delta: Custom expiration; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    token_payload = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    header = _b64url_encode(json.dumps({"alg": ALGORITHM, "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(token_payload).encode())
    signature = _sign(f"{header}.{body}", secret)
    return f"{header}.{body}.{signature}"


def decode_token(
    token: str,
    secret: str = SECRET_KEY,
) -> dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT string.
        secret: Signing secret (must match the one used to create the token).

    Returns:
        The decoded payload dict.

    Raises:
        ValueError: If the token is invalid, expired, or tampered with.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, body_b64, signature_b64 = parts

    # Verify signature
    expected_sig = _sign(f"{header_b64}.{body_b64}", secret)
    if not hmac.compare_digest(signature_b64, expected_sig):
        raise ValueError("Invalid token signature")

    # Decode payload
    payload = json.loads(_b64url_decode(body_b64))

    # Check expiration
    if "exp" in payload and payload["exp"] < time.time():
        raise ValueError("Token has expired")

    return payload


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def register_user(username: str, password: str, email: Optional[str] = None) -> dict[str, Any]:
    """
    Register a new user.

    Args:
        username: Unique username.
        password: Plain-text password (will be hashed).
        email: Optional email address.

    Returns:
        The created user dict (without password hash).

    Raises:
        ValueError: If the username is already taken.
    """
    if username in _users:
        raise ValueError(f"Username '{username}' already exists")

    user = {
        "username": username,
        "password_hash": _hash_password(password),
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _users[username] = user

    return {k: v for k, v in user.items() if k != "password_hash"}


def authenticate_user(username: str, password: str) -> Optional[dict[str, Any]]:
    """
    Verify credentials and return the user if valid.

    Args:
        username: The username.
        password: Plain-text password.

    Returns:
        User dict (without password hash) on success, None on failure.
    """
    user = _users.get(username)
    if user is None:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}


def login(username: str, password: str) -> dict[str, str]:
    """
    Authenticate and return access + refresh tokens.

    Args:
        username: The username.
        password: Plain-text password.

    Returns:
        Dict with 'access_token' and 'refresh_token'.

    Raises:
        ValueError: If credentials are invalid.
    """
    user = authenticate_user(username, password)
    if user is None:
        raise ValueError("Invalid username or password")

    access_token = create_token(
        {"sub": username, "type": "access"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_token(
        {"sub": username, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def refresh_access_token(refresh_token: str) -> str:
    """
    Issue a new access token from a valid refresh token.

    Args:
        refresh_token: A previously issued refresh token.

    Returns:
        A new access token string.

    Raises:
        ValueError: If the refresh token is invalid or not a refresh type.
    """
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    username = payload["sub"]
    if username not in _users:
        raise ValueError("User no longer exists")

    return create_token(
        {"sub": username, "type": "access"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


# ---------------------------------------------------------------------------
# Decorator for protecting routes / functions
# ---------------------------------------------------------------------------

def require_auth(func: Callable) -> Callable:
    """
    Decorator that requires a valid JWT access token.

    Expects the decorated function's first positional argument (after any
    'self') to be a token string.  Replaces that argument with the decoded
    user payload on success.

    Usage:
        @require_auth
        def get_profile(token_or_payload):
            ...

        # Call with a token string:
        get_profile("eyJ...")

        # The function receives the decoded payload instead.
    """

    @functools.wraps(func)
    def wrapper(token: str, *args: Any, **kwargs: Any) -> Any:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Access token required")
        return func(payload, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== JWT Auth Demo ===\n")

    # Register
    user = register_user("alice", "s3cret_pass!", email="alice@example.com")
    print(f"Registered: {user}")

    # Login
    tokens = login("alice", "s3cret_pass!")
    print(f"Tokens: access={tokens['access_token'][:40]}...")

    # Decode
    decoded = decode_token(tokens["access_token"])
    print(f"Decoded payload: {decoded}")

    # Protected function
    @require_auth
    def my_protected_route(payload: dict) -> str:
        return f"Hello, {payload['sub']}! You are authenticated."

    result = my_protected_route(tokens["access_token"])
    print(f"Protected route result: {result}")

    # Refresh
    new_access = refresh_access_token(tokens["refresh_token"])
    print(f"Refreshed token: {new_access[:40]}...")

    # Verify old password still works
    assert authenticate_user("alice", "s3cret_pass!") is not None
    assert authenticate_user("alice", "wrong_pass") is None
    print("\nAll checks passed!")
