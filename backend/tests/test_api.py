import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.schemas import ErrorResponse


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "proofloop"}


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("post", "/api/runs", {"target": "LedgerLite"}),
        ("get", "/api/runs/example-001", None),
        ("get", "/api/runs/example-001/events", None),
        ("get", "/api/runs/example-001/report", None),
        ("post", "/api/runs/example-001/challenge", {}),
        ("get", "/api/analytics", None),
    ],
)
def test_planned_routes_fail_explicitly(client, method, path, payload):
    response = client.request(method, path, json=payload)
    assert response.status_code == 501
    assert ErrorResponse.model_validate(response.json()).error.code == "not_implemented"
    assert "verified" not in response.json()


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
