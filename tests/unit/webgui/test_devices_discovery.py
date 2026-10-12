"""
Integration tests for device discovery WebGUI endpoints
"""
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from src.webgui.database import Database


@pytest.fixture
def app(tmp_path):
    """Create a Flask app for testing devices routes"""
    db_path = tmp_path / "data" / "webgui.db"
    buffer_db_path = tmp_path / "data" / "buffer.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    template_dir = tmp_path.parent / "src" / "webgui" / "templates"
    if not template_dir.exists():
        template_dir = tmp_path.parent.parent / "src" / "webgui" / "templates"
    if not template_dir.exists():
        template_dir = "/home/paperclip/.paperclip/instances/default/projects/c1c6aa82-3f9f-4f39-b1f9-4d9aa94f5d08/dff21b9a-f1da-4684-b613-c0d87b735c49/zk-collector/src/webgui/templates"

    app = Flask(__name__, template_folder=str(template_dir))
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True

    # Initialize database
    app.db = Database(db_path)
    import shutil

    migrations_src = "/home/paperclip/.paperclip/instances/default/projects/c1c6aa82-3f9f-4f39-b1f9-4d9aa94f5d08/dff21b9a-f1da-4684-b613-c0d87b735c49/zk-collector/migrations"
    migrations_dst = db_path.parent.parent / "migrations"
    if migrations_src and shutil.os.path.exists(migrations_src):
        shutil.copytree(migrations_src, migrations_dst, dirs_exist_ok=True)
    app.db.initialize()

    # Register blueprints
    from src.webgui.routes.devices import devices_bp

    app.register_blueprint(devices_bp, url_prefix="/devices")

    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


class TestDeviceDiscoveryAPI:
    """Tests for device discovery API endpoints"""

    @patch("src.webgui.routes.devices.discover_devices")
    def test_api_discover_devices_get_success(self, mock_discover, client):
        """Test GET /devices/api/devices/discover returns JSON list of DiscoveredDevice"""
        mock_discover.return_value = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "mac": "AA:BB:CC:DD:EE:FF",
                "model": "K40",
                "firmware": "6.60",
                "serial": "TEST123",
                "device_name": "Entrada Principal",
                "protocol": "udp",
                "already_configured": False,
            }
        ]

        response = client.get("/devices/api/devices/discover")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["devices"]) == 1
        assert data["devices"][0]["ip"] == "192.168.1.101"
        assert data["devices"][0]["model"] == "K40"

    @patch("src.webgui.routes.devices.discover_devices")
    def test_api_discover_devices_post_success(self, mock_discover, client):
        """Test POST /devices/api/devices/discover returns JSON list"""
        mock_discover.return_value = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "mac": "AA:BB:CC:DD:EE:FF",
                "model": "K40",
            },
            {
                "ip": "192.168.1.102",
                "port": 4370,
                "mac": "11:22:33:44:55:66",
                "model": "U160",
            },
        ]

        response = client.post(
            "/devices/api/devices/discover",
            json={"network": "192.168.1.0/24", "timeout": 3.0, "retries": 2, "fetch_details": True},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["devices"]) == 2
        # Both devices should be marked as not already configured (fresh DB)
        assert data["devices"][0]["already_configured"] is False
        assert data["devices"][1]["already_configured"] is False

    @patch("src.webgui.routes.devices.discover_devices")
    def test_api_discover_devices_empty_result(self, mock_discover, client):
        """Test discovery handles no devices found gracefully"""
        mock_discover.return_value = []

        response = client.get("/devices/api/devices/discover")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["devices"] == []
        assert "Descubiertos 0 dispositivo(s)" in data["message"]

    @patch("src.webgui.routes.devices.discover_devices")
    def test_api_discover_devices_network_error(self, mock_discover, client):
        """Test discovery handles network errors gracefully"""
        mock_discover.side_effect = Exception("Permission denied")

        response = client.get("/devices/api/devices/discover")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "Error en descubrimiento" in data["message"]

    @patch("src.webgui.routes.devices.discover_devices")
    def test_api_quick_discover(self, mock_discover, client):
        """Test quick discovery endpoint (UDP only)"""
        mock_discover.return_value = [
            {"ip": "192.168.1.101", "port": 4370, "mac": "AA:BB:CC:DD:EE:FF", "already_configured": False}
        ]

        response = client.post("/devices/api/devices/discover/quick", json={"network": "192.168.1.0/24"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        # Verify fetch_details=False was passed
        mock_discover.assert_called_once()
        args, kwargs = mock_discover.call_args
        assert kwargs.get("fetch_details") is False

    def test_api_add_from_discovery_success(self, client):
        """Test POST /devices/api/devices/add-from-discovery creates device with pre-filled config"""
        device_data = {
            "ip": "192.168.1.101",
            "mac": "AA:BB:CC:DD:EE:FF",
            "model": "K40",
            "firmware": "6.60",
            "serial": "TEST123",
            "device_name": "Entrada Principal",
            "name": "Mi K40",
            "location": "Recepción",
            "zone": "Zona 1",
            "port": 4370,
            "password": 0,
            "timeout": 5,
            "protocol": "tcp",
        }

        response = client.post("/devices/api/devices/add-from-discovery", json=device_data)

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "agregado exitosamente" in data["message"]
        assert "device_id" in data

        # Verify device was created in DB
        device = client.application.db.fetch_one("SELECT * FROM devices WHERE ip = ?", ("192.168.1.101",))
        assert device is not None
        assert device["name"] == "Mi K40"
        assert device["location"] == "Recepción"
        assert device["model"] == "K40"
        assert device["mac"] == "AA:BB:CC:DD:EE:FF"

    def test_api_add_from_discovery_missing_required_fields(self, client):
        """Test add-from-discovery requires ip and name"""
        response = client.post("/devices/api/devices/add-from-discovery", json={"name": "Test"})
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Campo requerido: ip" in data["message"]

        response = client.post("/devices/api/devices/add-from-discovery", json={"ip": "192.168.1.101"})
        assert response.status_code == 400
        data = response.get_json()
        assert "Campo requerido: name" in data["message"]

    def test_api_add_from_discovery_duplicate_ip(self, client):
        """Test add-from-discovery rejects duplicate IP"""
        # First device
        device_data = {"ip": "192.168.1.101", "name": "Test 1"}
        client.post("/devices/api/devices/add-from-discovery", json=device_data)

        # Second device with same IP
        device_data2 = {"ip": "192.168.1.101", "name": "Test 2"}
        response = client.post("/devices/api/devices/add-from-discovery", json=device_data2)

        assert response.status_code == 409
        data = response.get_json()
        assert data["success"] is False
        assert "Ya existe un dispositivo con esta IP" in data["message"]

    @patch("src.webgui.routes.devices.discover_devices")
    def test_discover_page_renders(self, mock_discover, client):
        """Test GET /devices/discover renders the discovery page"""
        response = client.get("/devices/discover")

        assert response.status_code == 200
        assert b"Descubrir Dispositivos en LAN" in response.data
        assert b"Escanear Red" in response.data
        assert b"Escaneo R" in response.data  # "Escaneo Rápido"

    @patch("src.webgui.routes.devices.discover_devices")
    def test_discover_endpoint_handles_timeout_error(self, mock_discover, client):
        """Test discovery handles timeout errors"""
        mock_discover.side_effect = TimeoutError("Discovery timeout")

        response = client.get("/devices/api/devices/discover")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False


class TestDeviceDiscoveryIntegration:
    """Integration tests with mocked ZKTeco response"""

    @patch("src.zk_client.discovery.ZKDiscovery.discover")
    def test_integration_with_mocked_zkteco_response(self, mock_discover, client):
        """Integration test with mocked ZKTeco UDP response"""
        # Mock the ZKDiscovery.discover method to simulate real device response
        mock_discover.return_value = [
            Mock(
                to_dict=Mock(
                    return_value={
                        "ip": "192.168.1.101",
                        "port": 4370,
                        "mac": "AA:BB:CC:DD:EE:FF",
                        "model": "K40",
                        "firmware": "6.60",
                        "serial": "TEST123",
                        "device_name": "Main Entrance",
                        "protocol": "udp",
                    }
                )
            )
        ]

        response = client.get("/devices/api/devices/discover")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["devices"]) == 1
        device = data["devices"][0]
        assert device["ip"] == "192.168.1.101"
        assert device["model"] == "K40"
        assert device["mac"] == "AA:BB:CC:DD:EE:FF"

    @patch("src.zk_client.discovery.ZKDiscovery.discover_with_details")
    def test_integration_with_mocked_tcp_details(self, mock_discover_details, client):
        """Integration test with mocked TCP detail fetch"""
        mock_discover_details.return_value = [
            Mock(
                to_dict=Mock(
                    return_value={
                        "ip": "192.168.1.101",
                        "port": 4370,
                        "mac": "AA:BB:CC:DD:EE:FF",
                        "model": "K40",
                        "firmware": "6.60",
                        "serial": "TEST123",
                        "device_name": "Main Entrance",
                        "protocol": "udp",
                    }
                )
            )
        ]

        response = client.post(
            "/devices/api/devices/discover",
            json={"fetch_details": True, "timeout": 5.0, "retries": 3},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["devices"][0]["model"] == "K40"
        assert data["devices"][0]["firmware"] == "6.60"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
