import pytest
from fastapi import HTTPException

from ai.main import auth


def test_local_development_allows_missing_secret(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_SECRET", raising=False)
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    auth(None)


def test_production_fails_closed_when_secret_is_missing(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_SECRET", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(HTTPException) as exc:
        auth(None)

    assert exc.value.status_code == 503


def test_auth_rejects_missing_or_wrong_header(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_SECRET", "expected-secret")
    monkeypatch.setenv("NODE_ENV", "development")

    with pytest.raises(HTTPException) as missing:
        auth(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as wrong:
        auth("wrong-secret")
    assert wrong.value.status_code == 401


def test_auth_accepts_matching_secret(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_SECRET", "expected-secret")
    monkeypatch.setenv("NODE_ENV", "development")

    auth("expected-secret")
