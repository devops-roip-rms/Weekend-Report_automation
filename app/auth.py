from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

UNSET_RUNTIME_VALUES = {"", "<TBD>", "<TO_VERIFY>", "UNKNOWN"}

CSRF_HEADER = "X-CSRF-Token"
CSRF_TTL_SECONDS = 3600

SESSION_COOKIE_NAME = "weekend_report_session"
SESSION_TTL_SECONDS = 14400  # 4 hours

PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000


def resolve_reviewer(request: Request, *, mutating: bool = False) -> str:
    mode = os.getenv("WEEKEND_REPORT_AUTH_MODE", "development").strip().lower()

    if mode in {"development", "dev", "local"}:
        return (
            request.headers.get("X-Reviewer")
            or os.getenv("WEEKEND_REPORT_DEV_REVIEWER", "anonymous")
            or "anonymous"
        )

    if mode != "production":
        raise HTTPException(status_code=503, detail=f"unsupported auth mode: {mode}")

    # Never allow the development identity mechanism in production.
    if request.headers.get("X-Reviewer"):
        raise HTTPException(
            status_code=400,
            detail="X-Reviewer is development-only and is rejected in production auth mode",
        )

    provider = os.getenv("WEEKEND_REPORT_AUTH_PROVIDER", "").strip().lower()
    if _is_unset(provider):
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_AUTH_PROVIDER is required in production auth mode",
        )

    reviewer = _reviewer_from_provider(request, provider)
    _enforce_authorized_reviewer(reviewer)
    return reviewer


def require_csrf_for_mutation(
    request: Request,
    reviewer: str | None = None,
) -> None:
    mode = os.getenv("WEEKEND_REPORT_AUTH_MODE", "development").strip().lower()

    if mode in {"development", "dev", "local"}:
        return

    if not reviewer:
        raise HTTPException(
            status_code=503,
            detail="reviewer is required for CSRF validation",
        )

    token = request.headers.get(CSRF_HEADER, "").strip()
    if not token or not _valid_csrf_token(token, reviewer):
        raise HTTPException(
            status_code=403,
            detail="missing or invalid CSRF token",
        )


def csrf_token_for_template(reviewer: str | None = None) -> str:
    mode = os.getenv("WEEKEND_REPORT_AUTH_MODE", "development").strip().lower()

    if mode in {"development", "dev", "local"}:
        return ""

    if not reviewer:
        raise HTTPException(
            status_code=503,
            detail="reviewer is required to issue CSRF token",
        )

    return issue_csrf_token(reviewer)


def issue_csrf_token(reviewer: str) -> str:
    payload = {
        "reviewer": reviewer,
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(18),
    }

    payload_b64 = _b64encode_json(payload)

    signature = hmac.new(
        _csrf_signing_key().encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_b64}.{signature}"


# ---------------------------------------------------------------------------
# Production authentication providers
# ---------------------------------------------------------------------------


def _reviewer_from_provider(request: Request, provider: str) -> str:
    if provider == "trusted_header":
        return _reviewer_from_trusted_header(request)

    if provider == "local_login":
        return _reviewer_from_local_session(request)

    raise HTTPException(
        status_code=503,
        detail=(
            f"unsupported production auth provider {provider!r}; "
            "supported providers are trusted_header and local_login"
        ),
    )


def _reviewer_from_trusted_header(request: Request) -> str:
    header_name = os.getenv(
        "WEEKEND_REPORT_AUTH_TRUSTED_HEADER",
        "",
    ).strip()

    if _is_unset(header_name):
        raise HTTPException(
            status_code=503,
            detail=("WEEKEND_REPORT_AUTH_TRUSTED_HEADER is required for trusted_header auth"),
        )

    reviewer = request.headers.get(header_name)

    if not reviewer:
        raise HTTPException(
            status_code=401,
            detail="reviewer identity header is missing",
        )

    reviewer = reviewer.strip()
    if not reviewer:
        raise HTTPException(
            status_code=401,
            detail="reviewer identity header is empty",
        )

    return reviewer


def _reviewer_from_local_session(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE_NAME, "").strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="authentication required",
        )

    reviewer = validate_session_token(token)

    if not reviewer:
        raise HTTPException(
            status_code=401,
            detail="invalid or expired authentication session",
        )

    return reviewer


# ---------------------------------------------------------------------------
# Local-login password verification
# ---------------------------------------------------------------------------


def authenticate_local_user(username: str, password: str) -> bool:
    username = username.strip()

    if not username or not password:
        return False

    users = _load_local_users()
    stored_hash = users.get(username)

    # Perform expensive work even when the username does not exist.
    # This reduces username-enumeration timing differences.
    if not isinstance(stored_hash, str):
        _dummy_password_check(password)
        return False

    return verify_password(password, stored_hash)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )

    return "$".join(
        [
            PASSWORD_HASH_SCHEME,
            str(PASSWORD_HASH_ITERATIONS),
            _b64encode_bytes(salt),
            _b64encode_bytes(digest),
        ]
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, expected_raw = encoded_hash.split("$", 3)

        if scheme != PASSWORD_HASH_SCHEME:
            return False

        iterations = int(iterations_raw)
        if iterations <= 0:
            return False

        salt = _b64decode_bytes(salt_raw)
        expected = _b64decode_bytes(expected_raw)

    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return hmac.compare_digest(actual, expected)


def _load_local_users() -> dict[str, str]:
    raw_path = os.getenv("WEEKEND_REPORT_LOCAL_USERS_FILE", "").strip()

    if _is_unset(raw_path):
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_LOCAL_USERS_FILE is required for local_login auth",
        )

    path = Path(raw_path)

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="local user database could not be read",
        ) from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=503,
            detail="local user database is not valid JSON",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=503,
            detail="local user database must contain a JSON object",
        )

    users = payload.get("users")

    if not isinstance(users, dict):
        raise HTTPException(
            status_code=503,
            detail="local user database must contain a users object",
        )

    normalized: dict[str, str] = {}

    for username, encoded_hash in users.items():
        if (
            isinstance(username, str)
            and username.strip()
            and isinstance(encoded_hash, str)
            and encoded_hash.strip()
        ):
            normalized[username.strip()] = encoded_hash.strip()

    return normalized


def _dummy_password_check(password: str) -> None:
    hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"weekend-report-dummy-salt",
        PASSWORD_HASH_ITERATIONS,
    )


# ---------------------------------------------------------------------------
# Local-login session
# ---------------------------------------------------------------------------


def issue_session_token(reviewer: str) -> str:
    now = int(time.time())

    payload = {
        "reviewer": reviewer,
        "iat": now,
        "exp": now + _session_ttl_seconds(),
        "nonce": secrets.token_urlsafe(18),
    }

    payload_b64 = _b64encode_json(payload)

    signature = hmac.new(
        _session_signing_key().encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def validate_session_token(token: str) -> str | None:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        _session_signing_key().encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = _b64decode_json(payload_b64)
    except (ValueError, json.JSONDecodeError):
        return None

    reviewer = payload.get("reviewer")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")

    if not isinstance(reviewer, str) or not reviewer.strip():
        return None

    if not isinstance(issued_at, int):
        return None

    if not isinstance(expires_at, int):
        return None

    now = int(time.time())

    # Reject malformed tokens claiming to have been created far in the future.
    if issued_at > now + 60:
        return None

    if expires_at <= now:
        return None

    if expires_at <= issued_at:
        return None

    return reviewer.strip()


def _session_signing_key() -> str:
    key = os.getenv("WEEKEND_REPORT_SESSION_SIGNING_KEY", "").strip()

    if _is_unset(key):
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_SESSION_SIGNING_KEY is required for local_login auth",
        )

    return key


def _session_ttl_seconds() -> int:
    raw = os.getenv(
        "WEEKEND_REPORT_SESSION_TTL_SECONDS",
        str(SESSION_TTL_SECONDS),
    ).strip()

    try:
        ttl = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_SESSION_TTL_SECONDS must be an integer",
        ) from exc

    if ttl <= 0:
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_SESSION_TTL_SECONDS must be greater than zero",
        )

    return ttl


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def _enforce_authorized_reviewer(reviewer: str) -> None:
    configured = os.getenv(
        "WEEKEND_REPORT_AUTHORIZED_REVIEWERS",
        "",
    ).strip()

    if _is_unset(configured):
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_AUTHORIZED_REVIEWERS is required for production access",
        )

    allowed = {item.strip() for item in configured.split(",") if item.strip()}

    if "*" not in allowed and reviewer not in allowed:
        raise HTTPException(
            status_code=403,
            detail="reviewer is not authorized",
        )


def enforce_authorized_reviewer(reviewer: str) -> None:
    """
    Public wrapper used by the local-login route after password verification.
    """
    _enforce_authorized_reviewer(reviewer)


# ---------------------------------------------------------------------------
# CSRF validation
# ---------------------------------------------------------------------------


def _csrf_signing_key() -> str:
    key = os.getenv("WEEKEND_REPORT_CSRF_SIGNING_KEY", "").strip()

    if _is_unset(key):
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_CSRF_SIGNING_KEY is required for production browser mutations",
        )

    return key


def _valid_csrf_token(token: str, reviewer: str) -> bool:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return False

    expected = hmac.new(
        _csrf_signing_key().encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return False

    try:
        payload = _b64decode_json(payload_b64)
    except (ValueError, json.JSONDecodeError):
        return False

    if payload.get("reviewer") != reviewer:
        return False

    issued_at = payload.get("iat")

    if not isinstance(issued_at, int):
        return False

    age = int(time.time()) - issued_at

    if age < 0:
        return False

    return age <= _csrf_ttl_seconds()


def _csrf_ttl_seconds() -> int:
    raw = os.getenv(
        "WEEKEND_REPORT_CSRF_TTL_SECONDS",
        str(CSRF_TTL_SECONDS),
    ).strip()

    try:
        ttl = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_CSRF_TTL_SECONDS must be an integer",
        ) from exc

    if ttl <= 0:
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_CSRF_TTL_SECONDS must be greater than zero",
        )

    return ttl


# ---------------------------------------------------------------------------
# Shared encoding helpers
# ---------------------------------------------------------------------------


def _is_unset(value: str | None) -> bool:
    return value is None or value.strip() in UNSET_RUNTIME_VALUES


def _b64encode_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode_json(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    payload = json.loads(decoded)

    if not isinstance(payload, dict):
        raise ValueError("token payload must be an object")

    return payload


def _b64encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode_bytes(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
