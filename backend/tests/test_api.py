import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PROOFLOOP_RUNS_DIR", str(tmp_path))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "proofloop"}


@pytest.mark.parametrize(
    "payload",
    [
        {"target": "https://unauthorized.example"},
        {"target": "LedgerLite", "max_attempts": 0},
        {"target": "LedgerLite", "api_key": "test-secret-must-not-echo"},
    ],
)
def test_invalid_run_requests_do_not_echo_input(client, payload):
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "test-secret-must-not-echo" not in response.text


def test_cors_allows_frontend(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unlisted_origin(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "https://unlisted.example", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_is_configurable(monkeypatch):
    monkeypatch.setenv("PROOFLOOP_CORS_ORIGINS", "http://localhost:5174")
    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5174"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"
