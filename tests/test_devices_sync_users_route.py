"""Tests de POST /devices/<id>/sync-users en redes sin ICMP (MYK-389).

Misma clase de bug que MYK-384: pyzk ejecuta helper.test_ping() (ICMP) dentro
de connect() salvo que se pase ommit_ping=True. sync-users es la unica ruta ZK
del WebGUI que seguia sin ommit_ping, fallando en redes que filtran ICMP
aunque el handshake TCP :4370 este abierto.

MYK-397: zk.user.User real NO trae user_role ni .get() — el route debe
tolerar ese shape (user_role ausente -> default 0) sin AttributeError.
"""

import pytest
from zk.exception import ZKError
from zk.user import User as PyzkUser


class FakeDeviceUser:
    """Usuario ZK con atributos como los devuelve pyzk (route lee attrs)."""

    def __init__(self, user_id, name, privilege=0, password="", group_id="", user_role=0):
        self.user_id = user_id
        self.name = name
        self.privilege = privilege
        self.password = password
        self.group_id = group_id
        self.user_role = user_role


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

    def get_users(self):
        return [
            FakeDeviceUser("1", "Ada Lovelace", privilege=14, group_id="1", user_role=0),
            FakeDeviceUser("2", "Grace Hopper", privilege=0, group_id="1", user_role=0),
        ]

    def disconnect(self):
        pass


class UnreachableFakeZK(IcmpBlockedFakeZK):
    """Dispositivo realmente inalcanzable: TCP tambien falla."""

    def connect(self):
        raise ZKError("can't reach device (connect error)")


class PyzkRealUserZK:
    """get_users devuelve objetos zk.user.User REALES del paquete instalado.

    Shape fiel a produccion: uid, name, privilege, password, group_id,
    user_id, card — SIN user_role y SIN .get() (causa del bug MYK-397).
    """

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
        pass

    def connect(self):
        return object()

    def get_users(self):
        return [
            PyzkUser(uid=1, name="Ada Lovelace", privilege=14, group_id="1", user_id="1"),
            PyzkUser(uid=2, name="Grace Hopper", privilege=0, group_id="1", user_id="2"),
        ]

    def disconnect(self):
        pass


@pytest.fixture
def icmp_blocked_zk(monkeypatch):
    IcmpBlockedFakeZK.instances = []
    monkeypatch.setattr("src.webgui.routes.devices.ZK", IcmpBlockedFakeZK)


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


def _rows_for(webgui_app, device_id):
    return webgui_app.db.fetch_all(
        "SELECT * FROM device_users WHERE device_id = ? ORDER BY user_id",
        (device_id,),
    )


def _logged_client(app):
    """Client con sesion WebGUI activa (MYK-451: sync-users requiere auth)."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "admin"
    return client


def test_sync_users_omits_ping_when_icmp_blocked(webgui_app, icmp_blocked_zk, device_row):
    """POST sync-users con ping bloqueado debe conectar via TCP y sincronizar (MYK-389)."""
    client = _logged_client(webgui_app)
    resp = client.post(f"/devices/{device_row['id']}/sync-users")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["synced_count"] == 2
    assert IcmpBlockedFakeZK.instances[-1].ommit_ping is True

    rows = _rows_for(webgui_app, device_row["id"])
    assert [r["user_id"] for r in rows] == ["1", "2"]
    assert rows[0]["name"] == "Ada Lovelace"
    assert rows[0]["privilege"] == 14


def test_sync_users_unreachable_reports_failure(webgui_app, monkeypatch, device_row):
    """Dispositivo TCP-inalcanzable: success=false y sin escrituras (no falso positivo)."""
    monkeypatch.setattr("src.webgui.routes.devices.ZK", UnreachableFakeZK)
    client = _logged_client(webgui_app)
    resp = client.post(f"/devices/{device_row['id']}/sync-users")

    body = resp.get_json()
    assert body["success"] is False
    assert _rows_for(webgui_app, device_row["id"]) == []


def test_sync_users_resync_updates_without_duplicates(webgui_app, icmp_blocked_zk, device_row):
    """Re-sincronizar actualiza los usuarios existentes en vez de duplicarlos."""
    client = _logged_client(webgui_app)
    first = client.post(f"/devices/{device_row['id']}/sync-users").get_json()
    assert first["success"] is True

    second = client.post(f"/devices/{device_row['id']}/sync-users").get_json()
    assert second["success"] is True
    assert second["synced_count"] == 2

    rows = _rows_for(webgui_app, device_row["id"])
    assert len(rows) == 2


def test_sync_users_unknown_device_404(webgui_app):
    """Dispositivo inexistente responde 404 sin tocar la red ZK."""
    client = _logged_client(webgui_app)
    resp = client.post("/devices/999999/sync-users")
    assert resp.status_code == 404


def test_sync_users_tolerates_real_pyzk_user(webgui_app, monkeypatch, device_row):
    """MYK-397: sync-users con zk.user.User real (sin user_role ni .get())."""
    monkeypatch.setattr("src.webgui.routes.devices.ZK", PyzkRealUserZK)
    client = _logged_client(webgui_app)
    resp = client.post(f"/devices/{device_row['id']}/sync-users")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True, body
    assert body["synced_count"] == 2

    rows = _rows_for(webgui_app, device_row["id"])
    assert [r["user_id"] for r in rows] == ["1", "2"]
    assert rows[0]["name"] == "Ada Lovelace"
    assert rows[0]["privilege"] == 14
    assert rows[0]["group_id"] == "1"
    assert int(rows[0]["user_role"]) == 0


def test_sync_users_resync_real_pyzk_user_no_duplicates(webgui_app, monkeypatch, device_row):
    """MYK-397: re-sync con User real actualiza sin duplicar ni fallar."""
    monkeypatch.setattr("src.webgui.routes.devices.ZK", PyzkRealUserZK)
    client = _logged_client(webgui_app)

    first = client.post(f"/devices/{device_row['id']}/sync-users").get_json()
    assert first["success"] is True

    second = client.post(f"/devices/{device_row['id']}/sync-users").get_json()
    assert second["success"] is True, second
    assert second["synced_count"] == 2

    rows = _rows_for(webgui_app, device_row["id"])
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"Ada Lovelace", "Grace Hopper"}
