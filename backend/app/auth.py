"""
Password hashing and JWT token logic for user authentication.

Passwords are hashed with bcrypt (never stored in plain text). JWTs carry
just the user id and an expiry, and are verified on every protected
request via the dependency in main.py.
"""
from __future__ import annotations

import os
import time

import bcrypt
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "fec3e6ca4aa90574f95db6dfad41bafbbb7821a264521063a1067c1f7b953cbc")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 60 * 60 * 24 * 30  # 30 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    payload = {"user_id": user_id, "exp": time.time() + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int | None:
    """Returns the user_id if the token is valid and unexpired, else None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("user_id")
    except jwt.PyJWTError:
        return None
