"""Tests de /devices/<id>/test y POST /devices/api/devices/test en redes sin ICMP (MYK-384).

pyzk ejecuta helper.test_ping() (ICMP) dentro de connect() salvo que se pase
ommit_ping=True. El endpoint de prueba del WebGUI debe omitir el ping y usar el
handshake TCP :4370 como probe real de alcanzabilidad.
"""

import pytest
from zk.exception import ZKError


class IcmpBlockedFakeZK:
    """Dispositivo ZK en red que bloquea ICMP: TCP :4370 OK, ping falla.

    Reproduce el comportamiento de pyzk: connect() hace test_ping() primero
    salvo ommit_ping=True.
    """

    instances = []

    def __init__(
        self,
        ip,
        port=4370,
        timeout=60,
        password=0,
        force_udp=False,
        ommit_ping=False,
        **kwargs,
    ):
        self.ip = ip
        self.ommit_ping = ommit_ping
        type(self).instances.append(self)

    def connect(self):
        if not self.ommit_ping:
            raise ZKError(f"can't reach device (ping {self.ip})")
        return object()

    def disconnect(self):
        pass

    def get_firmware_version(self):
        return "6.60"

    def get_serialnumber(self):
        return "EMU123456"

    def get_platform(self):
        return "ZEM800_TFT"


class UnreachableFakeZK(IcmpBlockedFakeZK):
    """Dispositivo realmente inalcanzable: TCP tambien falla."""

    def connect(self):
        raise ZKError("can't reach device (connect error)")


@pytest.fixture
def icmp_blocked_zk(monkeypatch):
    IcmpBlockedFakeZK.instances = []
    monkeypatch.setattr("src.webgui.routes.devices.ZK", IcmpBlockedFakeZK)


def _logged_client(app):
    """Client con sesion WebGUI activa (MYK-451: /test requiere auth)."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "admin"
    return client


@pytest.fixture
def device_row(webgui_app):
    webgui_app.db.insert(
        "devices",
        {
            "name": "Emulador sin ICMP",
            "location": "LAN",
            "zone": "",
            "address": "192.0.2.50",
            "port": 4370,
            "password": 0,
            "timeout": 5,
            "protocol": "tcp",
        },
    )
    return webgui_app.db.fetch_one("SELECT * FROM devices WHERE address = ?", ("192.0.2.50",))


def test_device_test_omits_ping_when_icmp_blocked(webgui_app, icmp_blocked_zk, device_row):
    """GET /devices/<id>/test con ping bloqueado debe conectar via TCP (MYK-384)."""
    client = _logged_client(webgui_app)
    resp = client.get(f"/devices/{device_row['id']}/test")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["device_info"]["serial"] == "EMU123456"
    assert body["device_info"]["firmware"] == "6.60"
    assert IcmpBlockedFakeZK.instances[-1].ommit_ping is True

    updated = webgui_app.db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_row["id"],))
    assert updated["status"] == "online"
    assert updated["serial_number"] == "EMU123456"
    assert updated["firmware_version"] == "6.60"


def test_device_test_unreachable_marks_offline(webgui_app, monkeypatch, device_row):
    """Dispositivo TCP-inalcanzable sigue quedando offline (no falso positivo)."""
    monkeypatch.setattr("src.webgui.routes.devices.ZK", UnreachableFakeZK)
    client = _logged_client(webgui_app)
    resp = client.get(f"/devices/{device_row['id']}/test")

    body = resp.get_json()
    assert body["success"] is False
    updated = webgui_app.db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_row["id"],))
    assert updated["status"] == "offline"


def test_api_devices_test_omits_ping(webgui_app, icmp_blocked_zk):
    """POST /devices/api/devices/test (form) tambien debe omitir el ping ICMP."""
    client = _logged_client(webgui_app)
    resp = client.post(
        "/devices/api/devices/test",
        json={
            "address": "192.0.2.50",
            "port": 4370,
            "timeout": 5,
            "password": 0,
            "protocol": "tcp",
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["device_info"]["serial"] == "EMU123456"
    assert IcmpBlockedFakeZK.instances[-1].ommit_ping is True
