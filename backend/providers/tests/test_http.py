import pytest

from backend.providers.errors import ProviderError
from backend.providers.http import HttpResponse, JsonHttpClient


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "authentication_failed", False),
        (403, "access_denied", False),
        (402, "credits_required", False),
        (429, "rate_limited", True),
        (503, "http_503", True),
        (302, "http_302", False),
    ],
)
def test_errors_are_redacted_and_retries_bounded(monkeypatch, status, code, retryable):
    monkeypatch.setattr("backend.providers.http.time.sleep", lambda _: None)
    calls = []

    def transport(*args):
        calls.append(args)
        return HttpResponse(status, b'{"error":"credential-secret"}')

    client = JsonHttpClient("provider", transport=transport)
    with pytest.raises(ProviderError, match=code) as error:
        client.request("POST", "https://example.invalid", {"Authorization": "secret"}, {})
    assert error.value.retryable == retryable
    assert len(calls) == (2 if retryable else 1)
    assert "secret" not in str(error.value)
    assert error.value.__cause__ is None


def test_timeout_then_success(monkeypatch):
    monkeypatch.setattr("backend.providers.http.time.sleep", lambda _: None)
    calls = []

    def transport(*args):
        calls.append(args)
        if len(calls) == 1:
            raise TimeoutError("secret")
        return HttpResponse(200, b'{"ok":true}')

    assert JsonHttpClient("p", transport=transport).request("GET", "https://e", {}) == {"ok": True}
    assert len(calls) == 2


@pytest.mark.parametrize(
    "body", [b"no json", b"[]", b'{"x":NaN}', b'{"x":1,"x":2}', b"\xff", b"x" * 1_000_001]
)
def test_invalid_or_oversized_responses(body):
    client = JsonHttpClient("p", transport=lambda *args: HttpResponse(200, body))
    with pytest.raises(ProviderError):
        client.request("GET", "https://e", {})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout": 0},
        {"timeout": 61},
        {"timeout": float("nan")},
        {"retries": -1},
        {"retries": 3},
        {"retries": True},
    ],
)
def test_invalid_budgets(kwargs):
    with pytest.raises(ValueError):
        JsonHttpClient("p", **kwargs)


def test_nonfinite_exponent_is_invalid_json():
    client = JsonHttpClient("p", transport=lambda *args: HttpResponse(200, b'{"x":1e400}'))
    with pytest.raises(ProviderError, match="invalid_json"):
        client.request("GET", "https://e", {})


def test_invalid_header_exception_is_sanitized():
    def transport(*args):
        raise ValueError("Invalid header value b'credential-secret'")

    client = JsonHttpClient("p", transport=transport)
    with pytest.raises(ProviderError, match="invalid_configuration") as error:
        client.request("GET", "https://e", {})
    assert "credential-secret" not in str(error.value)
    assert error.value.__suppress_context__


def test_https_transport_has_bounded_reads_and_closes_connection(monkeypatch):
    from backend.providers.http import https_request

    instances = []

    class Socket:
        def settimeout(self, timeout):
            assert 0 < timeout <= 5

    class Response:
        status = 200
        chunks = [b'{"ok":true}', b""]

        def read1(self, size):
            assert 1 <= size <= 65536
            return self.chunks.pop(0)

    class Connection:
        def __init__(self, host, port, timeout):
            self.host, self.port, self.timeout = host, port, timeout
            self.sock = Socket()
            self.closed = False
            instances.append(self)

        def connect(self):
            pass

        def request(self, method, path, body, headers):
            assert method == "GET" and path == "/v1/models?limit=1"

        def getresponse(self):
            return Response()

        def close(self):
            self.closed = True

    monkeypatch.setattr("backend.providers.http.http.client.HTTPSConnection", Connection)
    response = https_request("GET", "https://api.example/v1/models?limit=1", {}, None, 5)
    assert response.body == b'{"ok":true}'
    assert instances[0].host == "api.example" and instances[0].closed


@pytest.mark.parametrize(
    "url",
    ["http://api.example", "https://user:secret@api.example", "https://api.example/#fragment"],
)
def test_https_transport_rejects_insecure_origins(url):
    from backend.providers.http import https_request

    with pytest.raises(ValueError):
        https_request("GET", url, {}, None, 5)
