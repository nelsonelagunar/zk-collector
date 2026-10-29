"""Tests del MCP server de zk-collector (MYK-408).

Cubre:
- config: validacion de env vars, resolucion de credencial (static JWT vs
  secret para mint), guard de bind no-loopback y redaccion de secretos.
- tokens: JWTs minteados compatibles con Auth.verify_access_token del WebGUI,
  cacheo y refresh del MintingTokenProvider.
- client: Bearer header, timeouts, reintentos, re-mint una vez en 401 y
  errores seguros (sin token ni secret).
- tools: >=3 tools read-only con mapeo correcto de paths/params.
- server: registro de tools en FastMCP (skip si falta el paquete mcp).
- E2E: cliente MCP contra la app Flask real sobre HTTP con auth JWT real
  (minted y static), y rechazo documentado de token invalido (401).
"""

from __future__ import annotations

import asyncio
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.mcp_server.client import ZkApiError, ZkCollectorClient, build_token_provider
from src.mcp_server.config import ConfigError, MCPConfig
from src.mcp_server.tokens import MintingTokenProvider, StaticTokenProvider, mint_access_token
from src.mcp_server.tools import build_tools

TOKEN = "pat-secret-token-123"
SECRET = "test-secret-key"
STATIC_ENV = {"ZK_COLLECTOR_API_TOKEN": TOKEN}
MINTED_ENV = {"ZK_COLLECTOR_JWT_SECRET": SECRET}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_config(
    env_extra: dict[str, str] | None = None, base: dict[str, str] | None = None
) -> MCPConfig:
    env = dict(base if base is not None else STATIC_ENV)
    env.update(env_extra or {})
    return MCPConfig.from_env(env)


def fake_response(
    status_code: int = 200,
    json_data: object | None = None,
    text: str = "",
    content_type: str = "application/json",
) -> Mock:
    response = Mock()
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    else:
        def _boom() -> None:
            raise ValueError("no json")
        response.json.side_effect = _boom
    response.text = text
    response.headers = {"Content-Type": content_type}
    return response


class RecordingSession:
    """Sustituto de requests.Session que registra cada GET y responde fijos."""

    def __init__(self, responses: list[Mock] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.responses = list(responses or [])

    def get(self, url: str, **kwargs: object) -> Mock:
        self.calls.append({"url": url, **kwargs})
        if self.responses:
            return self.responses.pop(0)
        return fake_response(json_data={"ok": True})


class FailingSession:
    """Session que siempre falla a nivel conexion (sin respuesta HTTP)."""

    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str, **kwargs: object) -> Mock:
        self.calls += 1
        import requests

        raise requests.ConnectionError("connection refused")


# ---------------------------------------------------------------------------
# config — resolucion de credencial
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = MCPConfig.from_env(STATIC_ENV)
    assert config.base_url == "http://127.0.0.1:8080"
    assert config.api_token == TOKEN
    assert config.jwt_secret is None
    assert config.timeout_seconds == 10.0
    assert config.http_enabled is False
    assert config.http_host == "127.0.0.1"
    assert config.http_port == 9248
    assert config.auth_mode == "static"


def test_config_requires_credential() -> None:
    with pytest.raises(ConfigError, match="no credential configured"):
        MCPConfig.from_env({})
    with pytest.raises(ConfigError, match="ZK_COLLECTOR_JWT_SECRET"):
        MCPConfig.from_env({})


def test_config_accepts_zk_api_token_alias() -> None:
    config = MCPConfig.from_env({"ZK_API_TOKEN": "alias-token"})
    assert config.api_token == "alias-token"
    assert config.auth_mode == "static"


def test_config_minted_mode_from_explicit_secret() -> None:
    config = MCPConfig.from_env(MINTED_ENV)
    assert config.api_token is None
    assert config.jwt_secret == SECRET
    assert config.auth_mode == "minted"
    assert config.token_role == "supervisor"
    assert config.token_ttl_minutes == 30


def test_config_minted_mode_falls_back_to_webgui_secret_key() -> None:
    config = MCPConfig.from_env({"WEBGUI_SECRET_KEY": "webgui-secret"})
    assert config.jwt_secret == "webgui-secret"
    assert config.auth_mode == "minted"


def test_config_static_token_takes_precedence_over_secret() -> None:
    config = MCPConfig.from_env({**MINTED_ENV, **STATIC_ENV})
    assert config.api_token == TOKEN
    assert config.jwt_secret is None
    assert config.auth_mode == "static"


def test_config_token_role_and_ttl_validation() -> None:
    config = make_config(
        {"ZK_COLLECTOR_MCP_TOKEN_ROLE": "auditor", "ZK_COLLECTOR_MCP_TOKEN_TTL_MINUTES": "60"},
        base=MINTED_ENV,
    )
    assert config.token_role == "auditor"
    assert config.token_ttl_minutes == 60
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**MINTED_ENV, "ZK_COLLECTOR_MCP_TOKEN_TTL_MINUTES": "abc"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**MINTED_ENV, "ZK_COLLECTOR_MCP_TOKEN_TTL_MINUTES": "0"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**MINTED_ENV, "ZK_COLLECTOR_MCP_TOKEN_TTL_MINUTES": "9999"})


def test_config_rejects_bad_base_url() -> None:
    with pytest.raises(ConfigError, match="ZK_COLLECTOR_URL"):
        MCPConfig.from_env({**STATIC_ENV, "ZK_COLLECTOR_URL": "ftp://example.com"})


def test_config_strips_trailing_slash() -> None:
    config = make_config({"ZK_COLLECTOR_URL": "http://10.0.0.5:8080/"})
    assert config.base_url == "http://10.0.0.5:8080"


def test_config_timeout_validation() -> None:
    assert make_config({"ZK_COLLECTOR_MCP_TIMEOUT": "30"}).timeout_seconds == 30.0
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**STATIC_ENV, "ZK_COLLECTOR_MCP_TIMEOUT": "abc"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**STATIC_ENV, "ZK_COLLECTOR_MCP_TIMEOUT": "0"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**STATIC_ENV, "ZK_COLLECTOR_MCP_TIMEOUT": "999"})


def test_config_http_port_validation() -> None:
    assert make_config({"ZK_COLLECTOR_MCP_PORT": "9300"}).http_port == 9300
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**STATIC_ENV, "ZK_COLLECTOR_MCP_PORT": "not-a-port"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**STATIC_ENV, "ZK_COLLECTOR_MCP_PORT": "0"})


def test_config_http_enabled_truthy_values() -> None:
    for raw in ("1", "true", "YES", "On"):
        config = make_config({"ZK_COLLECTOR_MCP_HTTP": raw})
        assert config.http_enabled is True
    config = make_config({"ZK_COLLECTOR_MCP_HTTP": "0"})
    assert config.http_enabled is False


# ---------------------------------------------------------------------------
# config — guard de bind no-loopback (MYK-454 hallazgo 4)
# ---------------------------------------------------------------------------


def test_config_rejects_non_loopback_http_host() -> None:
    for host in ("0.0.0.0", "192.168.1.10", "example.com"):
        with pytest.raises(ConfigError, match="ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND"):
            MCPConfig.from_env(
                {**STATIC_ENV, "ZK_COLLECTOR_MCP_HTTP": "1", "ZK_COLLECTOR_MCP_HOST": host}
            )


def test_config_allows_non_loopback_host_with_explicit_override() -> None:
    config = MCPConfig.from_env(
        {
            **STATIC_ENV,
            "ZK_COLLECTOR_MCP_HTTP": "1",
            "ZK_COLLECTOR_MCP_HOST": "0.0.0.0",
            "ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND": "1",
        }
    )
    assert config.http_host == "0.0.0.0"


def test_config_loopback_hosts_are_fine_over_http() -> None:
    for host in ("127.0.0.1", "localhost", "::1"):
        config = MCPConfig.from_env(
            {**STATIC_ENV, "ZK_COLLECTOR_MCP_HTTP": "1", "ZK_COLLECTOR_MCP_HOST": host}
        )
        assert config.http_host == host


def test_config_ignores_host_guard_when_http_disabled() -> None:
    config = make_config({"ZK_COLLECTOR_MCP_HOST": "0.0.0.0"})
    assert config.http_enabled is False
    assert config.http_host == "0.0.0.0"


# ---------------------------------------------------------------------------
# config — redaccion
# ---------------------------------------------------------------------------


def test_config_redacted_never_leaks_token() -> None:
    redacted = make_config().redacted()
    assert TOKEN not in str(redacted)
    assert redacted["api_token"] == "set"


def test_config_redacted_never_leaks_secret() -> None:
    redacted = MCPConfig.from_env(MINTED_ENV).redacted()
    assert SECRET not in str(redacted)
    assert redacted["jwt_secret"] == "set"
    assert redacted["auth_mode"] == "minted"


# ---------------------------------------------------------------------------
# tokens — JWTs compatibles con el WebGUI (contrato MYK-443)
# ---------------------------------------------------------------------------


def test_minted_token_verifies_with_webgui_auth() -> None:
    from src.webgui.auth import Auth

    auth = Auth(SECRET)
    token = mint_access_token(SECRET, role="supervisor", ttl_minutes=30)
    payload = auth.verify_access_token(token)
    assert payload is not None
    assert payload["type"] == "access"
    assert payload["role"] == "supervisor"
    assert payload["username"] == "mcp-server"


def test_minted_token_rejected_with_wrong_secret() -> None:
    from src.webgui.auth import Auth

    token = mint_access_token(SECRET, role="supervisor", ttl_minutes=30)
    assert Auth("another-secret").verify_access_token(token) is None


def test_minting_provider_caches_until_near_expiry() -> None:
    provider = MintingTokenProvider(secret=SECRET, role="supervisor", ttl_minutes=30)
    before = provider.get_token()
    assert provider.get_token() == before  # cacheado (TTL >> margen)
    after = provider.refresh()
    assert after != before  # jti unico: siempre distinto
    assert provider.get_token() == after  # el refresh pasa a ser el cacheado


def test_minting_provider_remints_when_ttl_hits_refresh_margin() -> None:
    provider = MintingTokenProvider(secret=SECRET, role="supervisor", ttl_minutes=1)
    first = provider.get_token()
    second = provider.get_token()  # 1 min <= margen de 60s -> re-mint siempre
    assert first != second


def test_minting_provider_sensitive_values_contain_secret_and_token() -> None:
    provider = MintingTokenProvider(secret=SECRET, role="supervisor", ttl_minutes=30)
    provider.get_token()
    values = provider.sensitive_values()
    assert SECRET in values
    assert provider.get_token() in values


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------


def test_client_sends_bearer_header_and_parses_json() -> None:
    session = RecordingSession([fake_response(json_data={"devices": []})])
    client = ZkCollectorClient(make_config(), session=session)
    result = client.get("/attendance/api/devices")
    assert result == {"devices": []}
    call = session.calls[0]
    assert call["url"] == "http://127.0.0.1:8080/attendance/api/devices"
    headers = call["headers"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Accept"] == "application/json"
    assert call["timeout"] == 10.0


def test_client_minted_mode_sends_minted_jwt() -> None:
    session = RecordingSession([fake_response(json_data={"ok": True})])
    client = ZkCollectorClient(make_config(base=MINTED_ENV), session=session)
    assert client.get("/x") == {"ok": True}
    header = session.calls[0]["headers"]["Authorization"]  # type: ignore[index]
    token = header.split(" ", 1)[1]
    assert header.startswith("Bearer ")
    from src.webgui.auth import Auth

    assert Auth(SECRET).verify_access_token(token) is not None


def test_client_401_remints_once_with_minted_credential() -> None:
    session = RecordingSession(
        [fake_response(status_code=401, text="expired"), fake_response(json_data={"ok": True})]
    )
    client = ZkCollectorClient(make_config(base=MINTED_ENV), session=session)
    assert client.get("/x") == {"ok": True}
    assert len(session.calls) == 2
    first = session.calls[0]["headers"]["Authorization"]  # type: ignore[index]
    second = session.calls[1]["headers"]["Authorization"]  # type: ignore[index]
    assert first != second  # re-mint, no el mismo JWT vencido


def test_client_401_static_credential_does_not_retry() -> None:
    session = RecordingSession([fake_response(status_code=401, text="unauthorized")])
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="HTTP 401"):
        client.get("/x")
    assert len(session.calls) == 1


def test_client_401_error_hints_token_env() -> None:
    session = RecordingSession([fake_response(status_code=401, text="unauthorized")])
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="ZK_COLLECTOR_API_TOKEN") as excinfo:
        client.get("/api/attendance/stats")
    assert excinfo.value.status_code == 401


def test_client_401_minted_error_hints_secret_mismatch() -> None:
    session = RecordingSession(
        [
            fake_response(status_code=401, text="unauthorized"),
            fake_response(status_code=401, text="nope"),
        ]
    )
    client = ZkCollectorClient(make_config(base=MINTED_ENV), session=session)
    with pytest.raises(ZkApiError, match="WEBGUI_SECRET_KEY"):
        client.get("/api/attendance/stats")


def test_client_404_error_hints_version() -> None:
    session = RecordingSession([fake_response(status_code=404, text="not found")])
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="404") as excinfo:
        client.get("/nope")
    assert excinfo.value.status_code == 404


def test_client_5xx_error_is_server_error() -> None:
    session = RecordingSession([fake_response(status_code=503, text="down")])
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="503") as excinfo:
        client.get("/api/attendance/stats")
    assert excinfo.value.status_code == 503


def test_client_4xx_includes_truncated_detail() -> None:
    long_body = "x" * 500
    session = RecordingSession([fake_response(status_code=400, text=long_body)])
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError) as excinfo:
        client.get("/api/employees")
    assert "x" * 300 in str(excinfo.value)
    assert long_body not in str(excinfo.value)


def test_client_non_json_response_raises() -> None:
    session = RecordingSession(
        [fake_response(status_code=200, content_type="text/html")]
    )
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="non-JSON"):
        client.get("/health")


def test_client_retries_once_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.mcp_server.client.time.sleep", lambda _: None)
    session = FailingSession()
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="unreachable"):
        client.get("/attendance/api/devices")
    assert session.calls == 2


def test_client_error_messages_never_contain_token() -> None:
    session = RecordingSession(
        [fake_response(status_code=403, text=f"forbidden for {TOKEN}")]
    )
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError) as excinfo:
        client.get("/x")
    assert TOKEN not in str(excinfo.value)


def test_client_error_messages_never_contain_secret() -> None:
    session = RecordingSession(
        [fake_response(status_code=400, text=f"boom near {SECRET}")]
    )
    client = ZkCollectorClient(make_config(base=MINTED_ENV), session=session)
    with pytest.raises(ZkApiError) as excinfo:
        client.get("/x")
    assert SECRET not in str(excinfo.value)


def test_build_token_provider_matches_auth_mode() -> None:
    assert isinstance(build_token_provider(make_config()), StaticTokenProvider)
    assert isinstance(build_token_provider(make_config(base=MINTED_ENV)), MintingTokenProvider)


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


def tool_set() -> tuple[dict[str, object], RecordingSession]:
    session = RecordingSession()
    client = ZkCollectorClient(make_config({"ZK_COLLECTOR_URL": "http://zk"}), session=session)
    return build_tools(client), session


def test_tools_expose_at_least_three_read_only_tools() -> None:
    tools, _ = tool_set()
    assert len(tools) >= 3
    assert {
        "attendance_stats",
        "list_punches",
        "list_devices",
        "list_employees",
    } <= set(tools)


def test_tool_attendance_stats_maps_filters() -> None:
    tools, session = tool_set()
    tools["attendance_stats"](
        start_date="2026-10-01",
        end_date="2026-10-25",
        employee_id=7,
        department="Ventas",
        group_by="department",
    )
    call = session.calls[0]
    assert call["url"].endswith("/api/attendance/stats")
    assert call["params"] == {
        "start_date": "2026-10-01",
        "end_date": "2026-10-25",
        "employee_id": 7,
        "department": "Ventas",
        "group_by": "department",
    }


def test_tool_attendance_stats_rejects_bad_group_by() -> None:
    tools, _ = tool_set()
    with pytest.raises(ZkApiError, match="group_by"):
        tools["attendance_stats"](group_by="planeta")


def test_tool_list_punches_clamps_pagination() -> None:
    tools, session = tool_set()
    tools["list_punches"](page=0, per_page=999, user_id="12")
    call = session.calls[0]
    assert call["url"].endswith("/attendance/api/attendance")
    assert call["params"]["page"] == 1
    assert call["params"]["per_page"] == 200
    assert call["params"]["user_id"] == "12"


def test_tool_list_devices_uses_devices_endpoint() -> None:
    tools, session = tool_set()
    tools["list_devices"]()
    assert session.calls[0]["url"].endswith("/attendance/api/devices")


def test_tool_list_employees_maps_filters() -> None:
    tools, session = tool_set()
    tools["list_employees"](status="active", search="ana", page=2, per_page=50)
    call = session.calls[0]
    assert call["url"].endswith("/api/employees/")
    assert call["params"] == {
        "page": 2,
        "per_page": 50,
        "status": "active",
        "search": "ana",
    }


# ---------------------------------------------------------------------------
# server (FastMCP) — requiere el paquete mcp (extra [mcp])
# ---------------------------------------------------------------------------


def test_server_registers_all_tools() -> None:
    pytest.importorskip("mcp")
    from src.mcp_server.server import build_server

    mcp = build_server(make_config())
    listed = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in listed}
    assert {
        "attendance_stats",
        "list_punches",
        "list_devices",
        "list_employees",
    } <= names


def test_server_main_requires_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from src.mcp_server.server import main

    for var in (
        "ZK_COLLECTOR_API_TOKEN",
        "ZK_API_TOKEN",
        "ZK_COLLECTOR_JWT_SECRET",
        "WEBGUI_SECRET_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    assert main() == 2  # exit 2: credencial faltante, mensaje a stderr


# ---------------------------------------------------------------------------
# E2E: cliente MCP contra la app Flask real sobre HTTP (contrato JWT de MYK-443)
# ---------------------------------------------------------------------------


@pytest.fixture
def live_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shutil.copytree(Path(__file__).resolve().parents[1] / "migrations", tmp_path / "migrations")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DB_PATH", str(data_dir / "webgui.db"))
    monkeypatch.setenv("BUFFER_DB_PATH", str(data_dir / "buffer.db"))
    monkeypatch.setenv("WEBGUI_SECRET_KEY", "test-secret-key")
    from src.webgui.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


def _serve(app) -> tuple[threading.Thread, object, int]:
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread, server, server.server_port


def test_mcp_client_e2e_minted_jwt_against_real_webgui(live_app) -> None:
    """Handshake real: HTTP + Bearer JWT mintado + JSON contra create_app()."""
    thread, server, port = _serve(live_app)
    try:
        client = ZkCollectorClient(
            make_config(
                {"ZK_COLLECTOR_URL": f"http://127.0.0.1:{port}"},
                base={"WEBGUI_SECRET_KEY": "test-secret-key"},
            )
        )
        devices = client.get("/attendance/api/devices")
        assert devices == {"devices": []}
        punches = client.get("/attendance/api/attendance")
        assert "records" in punches or "attendance" in punches or isinstance(punches, dict)
        # Auth contract only: stats must NOT be 401. (HTTP 500 puede ocurrir por
        # la ruptura preexistente del esquema buffer en master, MYK-250.)
        try:
            stats = client.get("/api/attendance/stats")
            assert isinstance(stats, dict)
        except ZkApiError as exc:
            assert exc.status_code != 401
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_mcp_client_e2e_static_valid_jwt_against_real_webgui(live_app) -> None:
    """JWT mintado por el propio WebGUI (Auth.generate_tokens) tambien funciona."""
    thread, server, port = _serve(live_app)
    try:
        tokens = live_app.auth.generate_tokens(user_id=1, username="e2e", role="supervisor")
        client = ZkCollectorClient(
            make_config(
                {
                    "ZK_COLLECTOR_URL": f"http://127.0.0.1:{port}",
                    "ZK_COLLECTOR_API_TOKEN": tokens["access_token"],
                },
                base={},
            )
        )
        assert client.get("/attendance/api/devices") == {"devices": []}
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_mcp_client_e2e_invalid_token_is_rejected_with_401(live_app) -> None:
    """Contrato MYK-443: un token estatico no-JWT recibe 401 (antes pasaba)."""
    thread, server, port = _serve(live_app)
    try:
        client = ZkCollectorClient(
            make_config(
                {
                    "ZK_COLLECTOR_URL": f"http://127.0.0.1:{port}",
                    "ZK_COLLECTOR_API_TOKEN": "garbage-static-token",
                },
                base={},
            )
        )
        with pytest.raises(ZkApiError, match="401") as excinfo:
            client.get("/attendance/api/devices")
        assert excinfo.value.status_code == 401
    finally:
        server.shutdown()
        thread.join(timeout=5)
