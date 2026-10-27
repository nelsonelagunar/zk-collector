"""Configuration for the zk-collector MCP server (MYK-408).

Every setting comes from environment variables. Credentials (a static JWT or
the HS256 secret used to mint one) are read once into :class:`MCPConfig` and
are NEVER logged, returned by tools or included in error messages — the model
only sees API responses, never credentials.

Credential modes (exactly one is resolved at startup):
- ``static``: explicit JWT via ``ZK_COLLECTOR_API_TOKEN`` (or ``ZK_API_TOKEN``).
- ``minted``: shared HS256 secret via ``ZK_COLLECTOR_JWT_SECRET`` (or the
  WebGUI's own ``WEBGUI_SECRET_KEY``); the server mints short-lived access
  JWTs and refreshes them automatically.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_HTTP_HOST = "127.0.0.1"  # localhost only — never bind to a public interface
DEFAULT_HTTP_PORT = 9248
DEFAULT_TOKEN_ROLE = "supervisor"
DEFAULT_TOKEN_TTL_MINUTES = 30
MAX_TIMEOUT_SECONDS = 60.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_HTTP_PORT = 65535
MIN_HTTP_PORT = 1
MIN_TOKEN_TTL_MINUTES = 1
MAX_TOKEN_TTL_MINUTES = 1440

# Loopback bind targets that never expose the HTTP transport off-box.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "::ffff:127.0.0.1"})

BASE_URL_ENV = "ZK_COLLECTOR_URL"
TOKEN_ENVS = ("ZK_COLLECTOR_API_TOKEN", "ZK_API_TOKEN")
SECRET_ENVS = ("ZK_COLLECTOR_JWT_SECRET", "WEBGUI_SECRET_KEY")
TIMEOUT_ENV = "ZK_COLLECTOR_MCP_TIMEOUT"
HTTP_ENABLED_ENV = "ZK_COLLECTOR_MCP_HTTP"
HTTP_HOST_ENV = "ZK_COLLECTOR_MCP_HOST"
HTTP_PORT_ENV = "ZK_COLLECTOR_MCP_PORT"
HTTP_REMOTE_BIND_ENV = "ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND"
TOKEN_ROLE_ENV = "ZK_COLLECTOR_MCP_TOKEN_ROLE"
TOKEN_TTL_ENV = "ZK_COLLECTOR_MCP_TOKEN_TTL_MINUTES"

_TRUTHY = ("1", "true", "yes", "on")


class ConfigError(RuntimeError):
    """Raised when the MCP server configuration is invalid."""


@dataclass(frozen=True)
class MCPConfig:
    """Validated configuration for the MCP server and its API client."""

    base_url: str
    api_token: str | None
    jwt_secret: str | None
    token_role: str
    token_ttl_minutes: int
    timeout_seconds: float
    http_enabled: bool
    http_host: str
    http_port: int

    @property
    def auth_mode(self) -> str:
        """``"static"`` when an explicit JWT is set, ``"minted"`` otherwise."""
        return "static" if self.api_token else "minted"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> MCPConfig:
        """Build a config from ``env`` (defaults to ``os.environ``).

        Raises:
            ConfigError: if no credential is configured or a value is invalid.
        """
        env = os.environ if env is None else env

        base_url = (env.get(BASE_URL_ENV) or DEFAULT_BASE_URL).strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ConfigError(
                f"{BASE_URL_ENV} must start with http:// or https:// (got {base_url!r})"
            )

        api_token = cls._read_first(env, TOKEN_ENVS)
        jwt_secret: str | None = None
        if not api_token:
            jwt_secret = cls._read_first(env, SECRET_ENVS)
            if not jwt_secret:
                raise ConfigError(
                    "no credential configured: set ZK_COLLECTOR_API_TOKEN (a WebGUI "
                    "access JWT, sent as Bearer) or ZK_COLLECTOR_JWT_SECRET / "
                    "WEBGUI_SECRET_KEY so the MCP server can mint and auto-refresh "
                    "its own JWT. The WebGUI has no personal-access-token UI "
                    "(see docs/mcp.md)."
                )

        timeout = cls._read_timeout(env)
        http_enabled = cls._read_http_enabled(env)
        http_host = cls._read_http_host(env, http_enabled)
        http_port = cls._read_http_port(env)
        token_role = cls._read_token_role(env)
        token_ttl = cls._read_token_ttl(env)

        return cls(
            base_url=base_url,
            api_token=api_token,
            jwt_secret=jwt_secret,
            token_role=token_role,
            token_ttl_minutes=token_ttl,
            timeout_seconds=timeout,
            http_enabled=http_enabled,
            http_host=http_host,
            http_port=http_port,
        )

    @staticmethod
    def _read_first(env: Mapping[str, str], names: tuple[str, ...]) -> str | None:
        for var in names:
            value = (env.get(var) or "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _read_token_role(env: Mapping[str, str]) -> str:
        role = (env.get(TOKEN_ROLE_ENV) or DEFAULT_TOKEN_ROLE).strip()
        return role or DEFAULT_TOKEN_ROLE

    @staticmethod
    def _read_token_ttl(env: Mapping[str, str]) -> int:
        raw = (env.get(TOKEN_TTL_ENV) or "").strip()
        if not raw:
            return DEFAULT_TOKEN_TTL_MINUTES
        try:
            ttl = int(raw)
        except ValueError as exc:
            raise ConfigError(f"{TOKEN_TTL_ENV} must be an integer (got {raw!r})") from exc
        if not MIN_TOKEN_TTL_MINUTES <= ttl <= MAX_TOKEN_TTL_MINUTES:
            raise ConfigError(
                f"{TOKEN_TTL_ENV} must be between {MIN_TOKEN_TTL_MINUTES} and "
                f"{MAX_TOKEN_TTL_MINUTES} minutes (got {ttl})"
            )
        return ttl

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
    def _read_http_host(env: Mapping[str, str], http_enabled: bool) -> str:
        host = (env.get(HTTP_HOST_ENV) or DEFAULT_HTTP_HOST).strip() or DEFAULT_HTTP_HOST
        if not http_enabled or host in LOOPBACK_HOSTS:
            return host
        allow_remote = (env.get(HTTP_REMOTE_BIND_ENV) or "").strip().lower() in _TRUTHY
        if not allow_remote:
            raise ConfigError(
                f"{HTTP_HOST_ENV}={host!r} would expose the MCP tools off-box without "
                "transport auth. Bind a loopback host (default 127.0.0.1) or set "
                f"{HTTP_REMOTE_BIND_ENV}=1 explicitly and front it with a TLS reverse "
                "proxy (see docs/mcp.md)."
            )
        return host

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
        """Safe copy for logs: shows what is set, never any credential value."""
        return {
            "base_url": self.base_url,
            "auth_mode": self.auth_mode,
            "api_token": "set" if self.api_token else None,
            "jwt_secret": "set" if self.jwt_secret else None,
            "token_role": self.token_role,
            "token_ttl_minutes": self.token_ttl_minutes,
            "timeout_seconds": self.timeout_seconds,
            "http_enabled": self.http_enabled,
            "http_host": self.http_host,
            "http_port": self.http_port,
        }
