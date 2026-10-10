from fastapi.testclient import TestClient

from ai import main


client = TestClient(main.app)


def test_protected_route_rejects_missing_secret_when_configured(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_SECRET", "test-secret")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    response = client.post("/v1/probe", json={"media_path": "/does-not-exist"})
    assert response.status_code == 401


def test_protected_route_rejects_incorrect_secret(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_SECRET", "test-secret")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    response = client.post("/v1/probe", json={"media_path": "/does-not-exist"}, headers={"x-ai-secret": "wrong-secret"})
    assert response.status_code == 401


def test_protected_route_accepts_correct_secret(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_SECRET", "test-secret")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    response = client.post("/v1/probe", json={"media_path": "/does-not-exist"}, headers={"x-ai-secret": "test-secret"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Media file not found"


def test_production_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_SECRET", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    response = client.post("/v1/probe", json={"media_path": "/does-not-exist"})
    assert response.status_code == 503
    assert response.json()["detail"] == "AI service authentication is not configured"
