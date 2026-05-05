"""HTTP handler functions tying ``auth`` and ``db`` together.

This is the third fixture file; together these three modules give
the integration test enough surface area (>= 8000 tokens) and a
clean set of public function names to assert against via ast.parse.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Callable, Optional

from . import auth, db


_RATE_LIMIT_PER_MINUTE = 60
_RATE_BUCKET: dict[str, list[float]] = {}


class HandlerError(Exception):
    """Raised when a handler cannot serve the request and wants the
    framework to send a structured error response."""


def _now() -> float:
    return time.time()


def _json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandlerError(f"invalid JSON body: {exc}") from exc
    if not isinstance(decoded, dict):
        raise HandlerError("JSON body must be an object")
    return decoded


def _check_rate_limit(client_id: str) -> None:
    now = _now()
    bucket = _RATE_BUCKET.setdefault(client_id, [])
    bucket[:] = [t for t in bucket if now - t < 60]
    if len(bucket) >= _RATE_LIMIT_PER_MINUTE:
        raise HandlerError("rate limit exceeded")
    bucket.append(now)


def signup_handler(body: bytes, store: db.Store) -> dict[str, Any]:
    """POST /signup — create a credential and return the new user_id."""
    payload = _json_body(body)
    user_id = payload.get("user_id")
    password = payload.get("password")
    if not isinstance(user_id, str) or not isinstance(password, str):
        raise HandlerError("user_id and password must be strings")
    if len(password) < 8:
        raise HandlerError("password must be at least 8 characters")

    salt, pw_hash = auth.hash_password(password)
    cred = auth.Credential(
        user_id=user_id, salt=salt, pw_hash=pw_hash, created_at=_now()
    )
    store.table("credentials").upsert(user_id, asdict(cred) | {
        "salt": salt.hex(),
        "pw_hash": pw_hash.hex(),
    })
    return {"ok": True, "user_id": user_id}


def login_handler(body: bytes, store: db.Store) -> dict[str, Any]:
    """POST /login — return a session token on success."""
    payload = _json_body(body)
    user_id = payload.get("user_id")
    password = payload.get("password")
    if not isinstance(user_id, str) or not isinstance(password, str):
        raise HandlerError("user_id and password must be strings")
    _check_rate_limit(user_id)

    rec = store.table("credentials").get(user_id)
    cred = auth.Credential(
        user_id=user_id,
        salt=bytes.fromhex(rec.value["salt"]),
        pw_hash=bytes.fromhex(rec.value["pw_hash"]),
        created_at=rec.value["created_at"],
        locked_until=rec.value.get("locked_until", 0.0),
    )
    session = auth.authenticate(user_id, password, cred)
    store.table("sessions").upsert(session.token, asdict(session))
    return {"ok": True, "token": session.token,
            "expires_at": session.expires_at}


def logout_handler(token: str, store: db.Store) -> dict[str, Any]:
    """POST /logout — invalidate the session."""
    if not token:
        raise HandlerError("token required")
    try:
        store.table("sessions").soft_delete(token)
    except db.StoreError as exc:
        raise HandlerError(str(exc)) from exc
    return {"ok": True}


def whoami_handler(token: str, store: db.Store) -> dict[str, Any]:
    """GET /whoami — return the user_id associated with a token."""
    if not token:
        raise HandlerError("token required")
    rec = store.table("sessions").get(token)
    expires_at = rec.value["expires_at"]
    if _now() >= expires_at:
        raise HandlerError("session expired")
    return {"ok": True, "user_id": rec.value["user_id"],
            "expires_at": expires_at}


def list_users_handler(store: db.Store, page: int = 0,
                       page_size: int = 50) -> dict[str, Any]:
    """GET /users — paginated listing of credential keys."""
    table = store.table("credentials")
    rows = db.page_records(table, page=page, page_size=page_size)
    return {
        "ok": True,
        "users": [r.key for r in rows],
        "page": page,
        "page_size": page_size,
        "total": db.count_active(table),
    }


def change_password_handler(token: str, body: bytes,
                            store: db.Store) -> dict[str, Any]:
    """POST /password — update credential after re-auth."""
    payload = _json_body(body)
    new_password = payload.get("new_password")
    if not isinstance(new_password, str) or len(new_password) < 8:
        raise HandlerError("new_password must be a string of >= 8 chars")
    sess_rec = store.table("sessions").get(token)
    user_id = sess_rec.value["user_id"]
    salt, pw_hash = auth.hash_password(new_password)
    cred_rec = store.table("credentials").get(user_id)
    cred_rec.value["salt"] = salt.hex()
    cred_rec.value["pw_hash"] = pw_hash.hex()
    store.table("credentials").upsert(user_id, cred_rec.value)
    return {"ok": True}


def health_handler() -> dict[str, Any]:
    """GET /health — trivial liveness probe."""
    return {"ok": True, "now": _now()}


def dispatch(method: str, path: str, *, body: bytes = b"",
             token: str = "", store: Optional[db.Store] = None) -> dict[str, Any]:
    """Tiny router used by integration tests to call handlers by URL."""
    if store is None:
        raise HandlerError("store required")

    routes: dict[tuple[str, str], Callable[[], dict[str, Any]]] = {
        ("POST", "/signup"): lambda: signup_handler(body, store),
        ("POST", "/login"): lambda: login_handler(body, store),
        ("POST", "/logout"): lambda: logout_handler(token, store),
        ("GET", "/whoami"): lambda: whoami_handler(token, store),
        ("GET", "/users"): lambda: list_users_handler(store),
        ("POST", "/password"): lambda: change_password_handler(token, body, store),
        ("GET", "/health"): lambda: health_handler(),
    }
    handler = routes.get((method, path))
    if handler is None:
        raise HandlerError(f"no route for {method} {path}")
    return handler()
