from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.reclassification.utils.security import hash_password, sign_token, verify_password, verify_token


def test_password_hash_and_verify() -> None:
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_signed_token_round_trip() -> None:
    token = sign_token({"sub": "1", "role": "super_admin"}, "secret", expire_hours=8)
    payload = verify_token(token, "secret")
    assert payload["sub"] == "1"
    assert payload["role"] == "super_admin"


def test_signed_token_rejects_bad_signature() -> None:
    token = sign_token({"sub": "1"}, "secret")
    with pytest.raises(ValueError):
        verify_token(token + "x", "secret")
