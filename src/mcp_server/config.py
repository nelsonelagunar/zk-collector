"""Configuration for the zk-collector MCP server (MYK-408).

Every setting comes from environment variables. The API token is read once
into :class:`MCPConfig` and is NEVER logged, returned by tools or included
in error messages — the model only sees API responses, never credentials.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_HTTP_HOST = "127.0.0.1"  # localhost only — never bind to a public interface
DEFAULT_HTTP_PORT = 9248
MAX_TIMEOUT_SECONDS = 60.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_HTTP_PORT = 65535
MIN_HTTP_PORT = 1

BASE_URL_ENV = "ZK_COLLECTOR_URL"
TOKEN_ENVS = ("ZK_COLLECTOR_API_TOKEN", "ZK_API_TOKEN")
TIMEOUT_ENV = "ZK_COLLECTOR_MCP_TIMEOUT"
HTTP_ENABLED_ENV = "ZK_COLLECTOR_MCP_HTTP"
HTTP_HOST_ENV = "ZK_COLLECTOR_MCP_HOST"
HTTP_PORT_ENV = "ZK_COLLECTOR_MCP_PORT"

_TRUTHY = ("1", "true", "yes", "on")


class ConfigError(RuntimeError):
    """Raised when the MCP server configuration is invalid."""


@dataclass(frozen=True)
class MCPConfig:
    """Validated configuration for the MCP server and its API client."""

    base_url: str
    api_token: str
    timeout_seconds: float
    http_enabled: bool
    http_host: str
    http_port: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> MCPConfig:
        """Build a config from ``env`` (defaults to ``os.environ``).

        Raises:
            ConfigError: if the API token is missing or a value is invalid.
        """
        env = os.environ if env is None else env

        base_url = (env.get(BASE_URL_ENV) or DEFAULT_BASE_URL).strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ConfigError(
                f"{BASE_URL_ENV} must start with http:// or https:// (got {base_url!r})"
            )

        api_token = cls._read_token(env)
        timeout = cls._read_timeout(env)
        http_enabled = cls._read_http_enabled(env)
        http_host = (env.get(HTTP_HOST_ENV) or DEFAULT_HTTP_HOST).strip()
        http_port = cls._read_http_port(env)

        return cls(
            base_url=base_url,
            api_token=api_token,
            timeout_seconds=timeout,
            http_enabled=http_enabled,
            http_host=http_host,
            http_port=http_port,
        )

    @staticmethod
    def _read_token(env: Mapping[str, str]) -> str:
        for var in TOKEN_ENVS:
            token = (env.get(var) or "").strip()
            if token:
                return token
        raise ConfigError(
            "API token missing: set ZK_COLLECTOR_API_TOKEN to a personal access token "
            "(MYK-403 item 6). The MCP server forwards it as a Bearer header and never "
            "exposes it to the model."
        )

    @staticmethod
    def _read_timeout(env: Mapping[str, str]) -> float:
        raw = (env.get(TIMEOUT_ENV) or "").strip()
        if not raw:
            return DEFAULT_TIMEOUT_SECONDS
        try:
            timeout = float(raw)
        except ValueError as exc:
            raise ConfigError(f"{TIMEOUT_ENV} must be a number of seconds (got {raw!r})") from exc
        if not MIN_TIMEOUT_SECONDS <= timeout <= MAX_TIMEOUT_SECONDS:
            raise ConfigError(
                f"{TIMEOUT_ENV} must be between {MIN_TIMEOUT_SECONDS:.0f} and "
                f"{MAX_TIMEOUT_SECONDS:.0f} seconds (got {timeout})"
            )
        return timeout

    @staticmethod
    def _read_http_enabled(env: Mapping[str, str]) -> bool:
        return (env.get(HTTP_ENABLED_ENV) or "").strip().lower() in _TRUTHY

    @staticmethod
    def _read_http_port(env: Mapping[str, str]) -> int:
        raw = (env.get(HTTP_PORT_ENV) or "").strip()
        if not raw:
            return DEFAULT_HTTP_PORT
        try:
            port = int(raw)
        except ValueError as exc:
            raise ConfigError(f"{HTTP_PORT_ENV} must be an integer (got {raw!r})") from exc
        if not MIN_HTTP_PORT <= port <= MAX_HTTP_PORT:
            raise ConfigError(f"{HTTP_PORT_ENV} must be 1-65535 (got {port})")
        return port

    def redacted(self) -> dict[str, object]:
        """Safe copy for logs: shows whether a token is set, never its value."""
        return {
            "base_url": self.base_url,
            "api_token": "set" if self.api_token else "missing",
            "timeout_seconds": self.timeout_seconds,
            "http_enabled": self.http_enabled,
            "http_host": self.http_host,
            "http_port": self.http_port,
        }
