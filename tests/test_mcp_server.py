"""Tests del MCP server de zk-collector (MYK-408).

Cubre:
- config: validacion de env vars y redaccion del token.
- client: Bearer header, timeouts, reintentos y errores seguros (sin token).
- tools: >=3 tools read-only con mapeo correcto de paths/params.
- server: registro de tools en FastMCP (skip si falta el paquete mcp).
- E2E: cliente MCP contra la app Flask real sobre HTTP (handshake probado).
"""

from __future__ import annotations

import asyncio
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.mcp_server.client import ZkApiError, ZkCollectorClient
from src.mcp_server.config import ConfigError, MCPConfig
from src.mcp_server.tools import build_tools

TOKEN = "pat-secret-token-123"
BASE_ENV = {"ZK_COLLECTOR_API_TOKEN": TOKEN}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_config(**overrides: object) -> MCPConfig:
    env = dict(BASE_ENV)
    env.update({k: str(v) for k, v in overrides.items()})
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
# config
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = MCPConfig.from_env(BASE_ENV)
    assert config.base_url == "http://127.0.0.1:8080"
    assert config.api_token == TOKEN
    assert config.timeout_seconds == 10.0
    assert config.http_enabled is False
    assert config.http_host == "127.0.0.1"
    assert config.http_port == 9248


def test_config_requires_token() -> None:
    with pytest.raises(ConfigError, match="ZK_COLLECTOR_API_TOKEN"):
        MCPConfig.from_env({})


def test_config_accepts_zk_api_token_alias() -> None:
    config = MCPConfig.from_env({"ZK_API_TOKEN": "alias-token"})
    assert config.api_token == "alias-token"


def test_config_rejects_bad_base_url() -> None:
    with pytest.raises(ConfigError, match="ZK_COLLECTOR_URL"):
        MCPConfig.from_env({**BASE_ENV, "ZK_COLLECTOR_URL": "ftp://example.com"})


def test_config_strips_trailing_slash() -> None:
    config = make_config(**{"ZK_COLLECTOR_URL": "http://10.0.0.5:8080/"})
    assert config.base_url == "http://10.0.0.5:8080"


def test_config_timeout_validation() -> None:
    assert make_config(**{"ZK_COLLECTOR_MCP_TIMEOUT": "30"}).timeout_seconds == 30.0
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**BASE_ENV, "ZK_COLLECTOR_MCP_TIMEOUT": "abc"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**BASE_ENV, "ZK_COLLECTOR_MCP_TIMEOUT": "0"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**BASE_ENV, "ZK_COLLECTOR_MCP_TIMEOUT": "999"})


def test_config_http_port_validation() -> None:
    assert make_config(**{"ZK_COLLECTOR_MCP_PORT": "9300"}).http_port == 9300
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**BASE_ENV, "ZK_COLLECTOR_MCP_PORT": "not-a-port"})
    with pytest.raises(ConfigError):
        MCPConfig.from_env({**BASE_ENV, "ZK_COLLECTOR_MCP_PORT": "0"})


def test_config_http_enabled_truthy_values() -> None:
    for raw in ("1", "true", "YES", "On"):
        config = make_config(**{"ZK_COLLECTOR_MCP_HTTP": raw})
        assert config.http_enabled is True
    config = make_config(**{"ZK_COLLECTOR_MCP_HTTP": "0"})
    assert config.http_enabled is False


def test_config_redacted_never_leaks_token() -> None:
    redacted = make_config().redacted()
    assert TOKEN not in str(redacted)
    assert redacted["api_token"] == "set"


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


def test_client_401_error_hints_token_env() -> None:
    session = RecordingSession([fake_response(status_code=401, text="unauthorized")])
    client = ZkCollectorClient(make_config(), session=session)
    with pytest.raises(ZkApiError, match="ZK_COLLECTOR_API_TOKEN") as excinfo:
        client.get("/api/attendance/stats")
    assert excinfo.value.status_code == 401


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


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


def tool_set() -> tuple[dict[str, object], RecordingSession]:
    session = RecordingSession()
    client = ZkCollectorClient(make_config(**{"ZK_COLLECTOR_URL": "http://zk"}), session=session)
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


def test_server_main_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from src.mcp_server.server import main

    monkeypatch.delenv("ZK_COLLECTOR_API_TOKEN", raising=False)
    monkeypatch.delenv("ZK_API_TOKEN", raising=False)
    assert main() == 2  # exit 2: token faltante, mensaje a stderr


# ---------------------------------------------------------------------------
# E2E: cliente MCP contra la app Flask real sobre HTTP (MYK-408 handshake)
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


def test_mcp_client_e2e_against_real_webgui(live_app) -> None:
    """Handshake real: HTTP + Bearer + JSON contra create_app() sin mocks."""
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, live_app)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = ZkCollectorClient(
            make_config(**{"ZK_COLLECTOR_URL": f"http://127.0.0.1:{port}"})
        )
        devices = client.get("/attendance/api/devices")
        assert devices == {"devices": []}
        punches = client.get("/attendance/api/attendance")
        assert "records" in punches or "attendance" in punches or isinstance(punches, dict)
        stats = client.get("/api/attendance/stats")
        assert isinstance(stats, dict)
    finally:
        server.shutdown()
        thread.join(timeout=5)
