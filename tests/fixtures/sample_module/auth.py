"""Authentication utilities — password hashing, session tokens, and
permission checks.

This module is intentionally a self-contained example for fidelity
tests in cheap-llm-router. The business logic is illustrative.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

# Tunables — kept as module constants so they are easy to override in
# tests and so the fixture has stable identifiers to summarise.
PBKDF2_ITERATIONS = 200_000
SESSION_TTL_SECONDS = 8 * 3600
TOKEN_BYTES = 32
HASH_ALG = "sha256"


class AuthError(Exception):
    """Raised for any authentication-related failure that the caller
    is expected to surface to the user."""


@dataclass(frozen=True)
class Credential:
    """Stored credential for a single user."""

    user_id: str
    salt: bytes
    pw_hash: bytes
    created_at: float
    locked_until: float = 0.0


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """Hash a plaintext password with PBKDF2.

    Returns ``(salt, derived_key)``. If ``salt`` is omitted, a fresh
    16-byte salt is generated.
    """
    if not isinstance(password, str) or not password:
        raise AuthError("password must be a non-empty string")
    salt = salt if salt is not None else os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        HASH_ALG, password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return salt, derived


def verify_password(password: str, credential: Credential) -> bool:
    """Constant-time check that ``password`` matches the stored credential."""
    _, candidate = hash_password(password, credential.salt)
    return hmac.compare_digest(candidate, credential.pw_hash)


def make_session_token() -> str:
    """Return a URL-safe random session token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


@dataclass
class Session:
    token: str
    user_id: str
    created_at: float
    expires_at: float
    last_seen: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def touch(self) -> None:
        self.last_seen = time.time()


def create_session(user_id: str) -> Session:
    """Construct a new session for the given user with default TTL."""
    now = time.time()
    return Session(
        token=make_session_token(),
        user_id=user_id,
        created_at=now,
        expires_at=now + SESSION_TTL_SECONDS,
        last_seen=now,
    )


def renew_session(session: Session, ttl_seconds: int = SESSION_TTL_SECONDS) -> Session:
    """Return a copy of ``session`` with its TTL extended."""
    if session.is_expired:
        raise AuthError("cannot renew an expired session")
    now = time.time()
    return Session(
        token=session.token,
        user_id=session.user_id,
        created_at=session.created_at,
        expires_at=now + ttl_seconds,
        last_seen=now,
    )


def lock_account(credential: Credential, until_seconds_from_now: float) -> Credential:
    """Return a copy of ``credential`` locked for the given duration."""
    if until_seconds_from_now < 0:
        raise AuthError("lock duration must be non-negative")
    return Credential(
        user_id=credential.user_id,
        salt=credential.salt,
        pw_hash=credential.pw_hash,
        created_at=credential.created_at,
        locked_until=time.time() + until_seconds_from_now,
    )


def is_locked(credential: Credential) -> bool:
    """True if the credential's lock has not yet expired."""
    return credential.locked_until > time.time()


def authenticate(user_id: str, password: str,
                 credential: Credential) -> Session:
    """Full happy-path: lock check + verify + new session.

    Raises AuthError on lockout or wrong password.
    """
    if is_locked(credential):
        remaining = int(credential.locked_until - time.time())
        raise AuthError(f"account locked for another {remaining}s")
    if credential.user_id != user_id:
        raise AuthError("user_id mismatch")
    if not verify_password(password, credential):
        raise AuthError("invalid password")
    return create_session(user_id)
