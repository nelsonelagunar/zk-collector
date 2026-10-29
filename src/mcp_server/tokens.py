"""Bearer credential providers for the MCP server (MYK-408 fix).

The WebGUI validates ``Authorization: Bearer`` as a JWT HS256 access token
(``Auth.verify_access_token`` in ``src/webgui/auth.py``, 30-minute default
expiry) — there is no personal-access-token UI. The MCP server therefore
supports two credential modes:

- **static**: an explicit JWT supplied via ``ZK_COLLECTOR_API_TOKEN``;
- **minted** (recommended): the server holds the same HS256 secret as the
  WebGUI and mints its own short-lived access tokens, refreshing them before
  expiry and once on HTTP 401.

The secret and every minted token are process-private: they are never logged,
returned by tools, or included in error messages.
"""

from __future__ import annotations

import secrets
import threading
from datetime import UTC, datetime, timedelta

import jwt

# Refresh a cached token this many seconds before its ``exp`` claim.
REFRESH_MARGIN_SECONDS = 60

MCP_TOKEN_USERNAME = "mcp-server"
MCP_TOKEN_USER_ID = 0


def mint_access_token(
    secret: str,
    role: str,
    ttl_minutes: int,
    username: str = MCP_TOKEN_USERNAME,
    user_id: int = MCP_TOKEN_USER_ID,
    now: datetime | None = None,
) -> str:
    """Mint a WebGUI-compatible access JWT (HS256, ``type=access``).

    The payload mirrors ``Auth.generate_tokens`` access tokens so the
    WebGUI's ``api_require`` middleware accepts it.
    """
    issued_at = now or datetime.now(UTC)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": issued_at + timedelta(minutes=ttl_minutes),
        "iat": issued_at,
        "jti": secrets.token_hex(8),  # uniqueness even within the same second
        "type": "access",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class StaticTokenProvider:
    """Returns the operator-supplied JWT unchanged (no refresh possible)."""

    refreshable = False

    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self) -> str:
        return self._token

    def refresh(self) -> str:
        return self._token

    def sensitive_values(self) -> tuple[str, ...]:
        return (self._token,)


class MintingTokenProvider:
    """Mints and caches short-lived access JWTs; thread-safe.

    ``get_token`` re-mints automatically when the cached token is within
    :data:`REFRESH_MARGIN_SECONDS` of expiry; ``refresh`` forces a fresh mint
    (used once per request on HTTP 401).
    """

    refreshable = True

    def __init__(self, secret: str, role: str, ttl_minutes: int) -> None:
        self._secret = secret
        self._role = role
        self._ttl_minutes = ttl_minutes
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_exp: datetime | None = None

    def get_token(self) -> str:
        with self._lock:
            if self._token is None or self._expiring():
                return self._mint()
            return self._token

    def refresh(self) -> str:
        """Discard the cached token and mint a fresh one."""
        with self._lock:
            return self._mint()

    def _mint(self) -> str:
        token = mint_access_token(self._secret, self._role, self._ttl_minutes)
        self._token = token
        self._token_exp = datetime.now(UTC) + timedelta(
            minutes=self._ttl_minutes
        )
        return token

    def _expiring(self) -> bool:
        if self._token_exp is None:
            return True
        remaining = self._token_exp - datetime.now(UTC)
        return remaining.total_seconds() <= REFRESH_MARGIN_SECONDS

    def sensitive_values(self) -> tuple[str, ...]:
        with self._lock:
            token = self._token
        values = [self._secret]
        if token:
            values.append(token)
        return tuple(values)
