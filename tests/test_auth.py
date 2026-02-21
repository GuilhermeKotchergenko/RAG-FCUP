"""
tests/test_auth.py

Unit tests for the Magic Link authentication logic.
"""

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

# ── Setup ──────────────────────────────────────────────────────────────────────

SECRET_KEY = "test-secret-key"
ALGORITHM = "HS256"


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", SECRET_KEY)
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "fc.up.pt")
    monkeypatch.setenv("SIMULATE_EMAIL", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


# ── Domain Validation ─────────────────────────────────────────────────────────


def test_valid_fcup_email():
    from api.auth import _validate_domain
    # Should not raise
    _validate_domain("student@fc.up.pt")


def test_invalid_domain_raises():
    from api.auth import _validate_domain
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _validate_domain("student@gmail.com")
    assert exc_info.value.status_code == 400
    assert "fc.up.pt" in exc_info.value.detail


def test_invalid_domain_up_pt_raises():
    """up.pt alone should not be accepted — domain must be exactly fc.up.pt."""
    from api.auth import _validate_domain
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _validate_domain("student@up.pt")


# ── Token Generation ──────────────────────────────────────────────────────────


def test_token_contains_email_and_type():
    from api.auth import _create_token
    token = _create_token("student@fc.up.pt")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "student@fc.up.pt"
    assert payload["type"] == "magic_link"


def test_token_has_expiry():
    from api.auth import _create_token
    import importlib, api.auth as auth_module
    token = _create_token("student@fc.up.pt")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert "exp" in payload
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    now = datetime.now(UTC)
    assert now < exp < now + timedelta(minutes=20)


# ── Token Hash ────────────────────────────────────────────────────────────────


def test_token_hash_deterministic():
    from api.auth import _hash_token
    assert _hash_token("abc") == _hash_token("abc")


def test_different_tokens_different_hashes():
    from api.auth import _hash_token
    assert _hash_token("abc") != _hash_token("xyz")


# ── Simulation Mode ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simulate_email_prints_link(capsys):
    from api.auth import _send_or_simulate
    await _send_or_simulate("student@fc.up.pt", "http://localhost:8000/verify?token=abc")
    captured = capsys.readouterr()
    assert "http://localhost:8000/verify?token=abc" in captured.out
