"""HTTP client for the zk-collector REST/JSON API used by MCP tools.

Integration contract (MYK-408):
- Auth: ``Authorization: Bearer <jwt>`` on every call. The JWT is either
  operator-supplied (``ZK_COLLECTOR_API_TOKEN``) or minted from the shared
  HS256 secret and auto-refreshed — credentials never logged, never returned
  to the model, sanitized out of error details.
- Timeouts: requests timeout after ``config.timeout_seconds`` (default 10s).
- Retries: one retry (0.5s backoff) on connection errors — GETs are
  idempotent; HTTP error statuses are NOT retried. Exception: a single
  401 re-mint + retry when the credential is minted (expired access token).
- Errors: raised as :class:`ZkApiError` with a safe, credential-free message.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from .config import MCPConfig
from .tokens import MintingTokenProvider, StaticTokenProvider

RETRY_BACKOFF_SECONDS = 0.5
MAX_ATTEMPTS = 2
MAX_DETAIL_CHARS = 300


class ZkApiError(RuntimeError):
    """A zk-collector API call failed (safe to show to the model)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_token_provider(config: MCPConfig) -> StaticTokenProvider | MintingTokenProvider:
    """Pick the credential provider declared by ``config``."""
    if config.api_token:
        return StaticTokenProvider(config.api_token)
    assert config.jwt_secret is not None  # validated in MCPConfig.from_env
    return MintingTokenProvider(
        secret=config.jwt_secret,
        role=config.token_role,
        ttl_minutes=config.token_ttl_minutes,
    )


class ZkCollectorClient:
    """Thin requests-based client over the WebGUI JSON endpoints."""

    def __init__(
        self,
        config: MCPConfig,
        session: requests.Session | None = None,
        token_provider: StaticTokenProvider | MintingTokenProvider | None = None,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._provider = token_provider or build_token_provider(config)

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` with Bearer auth; returns parsed JSON."""
        url = f"{self._config.base_url}{path}"
        last_error: requests.RequestException | None = None
        reminted = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            token = self._provider.get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
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
            if response.status_code == 401 and self._provider.refreshable and not reminted:
                # Minted JWT rejected (e.g. expired/clock drift): mint once, retry.
                reminted = True
                self._provider.refresh()
                continue
            return self._handle_response(response)
        raise ZkApiError(f"zk-collector unreachable at {self._config.base_url}") from last_error

    def _handle_response(self, response: requests.Response) -> Any:
        if response.status_code == 401:
            raise ZkApiError(
                f"zk-collector rejected the credential (HTTP 401): "
                f"{self._unauthorized_hint()}",
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

    def _unauthorized_hint(self) -> str:
        if self._config.auth_mode == "static":
            return (
                "check ZK_COLLECTOR_API_TOKEN — it must be a valid WebGUI access JWT "
                "(HS256) and WebGUI access tokens expire; re-mint it"
            )
        return (
            "check that ZK_COLLECTOR_JWT_SECRET (or WEBGUI_SECRET_KEY) matches the "
            "secret the WebGUI signs its access tokens with"
        )

    def _safe_detail(self, response: requests.Response) -> str:
        body = (response.text or "").strip().replace("\n", " ")
        for value in self._provider.sensitive_values():
            if value and value in body:
                body = body.replace(value, "[redacted]")
        if len(body) > MAX_DETAIL_CHARS:
            body = f"{body[:MAX_DETAIL_CHARS]}…"
        return body or "no detail"
