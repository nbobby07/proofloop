"""Dependency-free HTTPS transport with size, time, and retry budgets.

No redirects or environment proxies. Adapters select fixed official origins.
"""

import http.client
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.providers.errors import ProviderError

MAX_BYTES = 1_000_000


def decode_json(data: str | bytes, provider: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non-finite number")

    def finite_number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite number")
        return parsed

    try:
        return json.loads(
            data, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_number
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProviderError(provider, "invalid_json") from None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


Transport = Callable[[str, str, dict[str, str], bytes | None, float], HttpResponse]


def https_request(method, url, headers, body, timeout) -> HttpResponse:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.fragment:
        raise ValueError("Only HTTPS provider origins are supported")
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=timeout)
    try:
        connection.connect()
        connection.sock.settimeout(max(0.001, deadline - time.monotonic()))
        connection.request(
            method,
            parts.path + ("?" + parts.query if parts.query else ""),
            body=body,
            headers=headers,
        )
        connection.sock.settimeout(max(0.001, deadline - time.monotonic()))
        response = connection.getresponse()
        chunks = []
        size = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                return HttpResponse(response.status, b"".join(chunks))
            size += len(chunk)
            if size > MAX_BYTES:
                raise ProviderError("http", "response_too_large")
            chunks.append(chunk)
    finally:
        connection.close()


class JsonHttpClient:
    def __init__(
        self,
        provider: str,
        *,
        timeout: float = 30,
        retries: int = 1,
        transport: Transport = https_request,
    ):
        if not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("timeout must be in (0, 60]")
        if type(retries) is not int or not 0 <= retries <= 2:
            raise ValueError("retries must be 0..2")
        self.provider = provider
        self.timeout = timeout
        self.retries = retries
        self.transport = transport

    def request(self, method: str, url: str, headers: dict[str, str], payload=None):
        try:
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ProviderError(self.provider, "invalid_input") from None
        if body is not None and len(body) > MAX_BYTES:
            raise ProviderError(self.provider, "request_too_large")
        for attempt in range(self.retries + 1):
            try:
                response = self.transport(method, url, headers, body, self.timeout)
            except TimeoutError:
                error = ProviderError(self.provider, "timeout", retryable=True)
            except (OSError, http.client.HTTPException):
                error = ProviderError(self.provider, "network_error", retryable=True)
            except ValueError:
                # Invalid header values can embed the credential in http.client's exception.
                raise ProviderError(self.provider, "invalid_configuration") from None
            except ProviderError as exc:
                raise ProviderError(self.provider, exc.code, retryable=exc.retryable) from None
            else:
                if 200 <= response.status < 300:
                    if len(response.body) > MAX_BYTES:
                        raise ProviderError(self.provider, "response_too_large")
                    result = decode_json(response.body, self.provider)
                    if not isinstance(result, dict):
                        raise ProviderError(self.provider, "invalid_response")
                    return result
                code = {
                    401: "authentication_failed",
                    403: "access_denied",
                    402: "credits_required",
                    429: "rate_limited",
                }.get(response.status, f"http_{response.status}")
                error = ProviderError(
                    self.provider, code, retryable=response.status in {408, 429, 500, 502, 503, 504}
                )
            if not error.retryable or attempt == self.retries:
                raise error from None
            time.sleep(0.25 * (2**attempt))
        raise AssertionError("unreachable")
