"""HTTP client for the zk-collector REST/JSON API used by MCP tools.

Integration contract (MYK-408):
- Auth: ``Authorization: Bearer <token>`` on every call (token from config,
  never logged, never returned to the model).
- Timeouts: requests timeout after ``config.timeout_seconds`` (default 10s).
- Retries: one retry (0.5s backoff) on connection errors — GETs are
  idempotent; HTTP error statuses are NOT retried.
- Errors: raised as :class:`ZkApiError` with a safe, token-free message.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from .config import MCPConfig

RETRY_BACKOFF_SECONDS = 0.5
MAX_ATTEMPTS = 2
MAX_DETAIL_CHARS = 300


class ZkApiError(RuntimeError):
    """A zk-collector API call failed (safe to show to the model)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ZkCollectorClient:
    """Thin requests-based client over the WebGUI JSON endpoints."""

    def __init__(self, config: MCPConfig, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` with Bearer auth; returns parsed JSON."""
        url = f"{self._config.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._config.api_token}",
            "Accept": "application/json",
        }
        last_error: requests.RequestException | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._config.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                raise ZkApiError(
                    f"zk-collector unreachable at {self._config.base_url} "
                    f"({type(exc).__name__})"
                ) from exc
            return self._handle_response(response)
        raise ZkApiError(f"zk-collector unreachable at {self._config.base_url}") from last_error

    def _handle_response(self, response: requests.Response) -> Any:
        if response.status_code == 401:
            raise ZkApiError(
                "zk-collector rejected the token (HTTP 401): check ZK_COLLECTOR_API_TOKEN",
                status_code=401,
            )
        if response.status_code == 404:
            raise ZkApiError(
                f"endpoint not found (HTTP 404) on {self._config.base_url}: "
                "is this zk-collector version recent enough?",
                status_code=404,
            )
        if response.status_code >= 500:
            raise ZkApiError(
                f"zk-collector server error (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ZkApiError(
                f"request rejected (HTTP {response.status_code}): "
                f"{self._safe_detail(response)}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ZkApiError(
                "zk-collector returned a non-JSON response "
                f"(HTTP {response.status_code}, content-type "
                f"{response.headers.get('Content-Type', 'unknown')})"
            ) from exc

    def _safe_detail(self, response: requests.Response) -> str:
        body = (response.text or "").strip().replace("\n", " ")
        token = self._config.api_token
        if token and token in body:
            body = body.replace(token, "[redacted]")
        if len(body) > MAX_DETAIL_CHARS:
            body = f"{body[:MAX_DETAIL_CHARS]}…"
        return body or "no detail"
