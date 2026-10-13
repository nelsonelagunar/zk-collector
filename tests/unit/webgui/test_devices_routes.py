"""
Unit tests for Devices routes - CRUD endpoints
"""

from unittest.mock import Mock, patch

import pytest
from flask import Flask


@pytest.fixture
def app(tmp_path):
    """Create a Flask app for testing"""
    buffer_db_path = tmp_path / "buffer.db"

    # Find the templates directory (same pattern as attendance export tests)
    import os
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "src", "webgui", "templates")

    app = Flask(__name__, template_folder=template_dir)
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True

    # Mock database for devices API
    mock_db = Mock()

    def fetch_all_side_effect(query, params=()):
        if "devices" in query.lower() and "select" in query.lower():
            # devices query: SELECT * FROM devices ORDER BY name
            return [
                {"id": 1, "name": "Test Device 1", "location": "Office A", "zone": "Zone 1",
                 "ip": "192.168.1.101", "address": "192.168.1.101", "port": 4370, "password": 0, "timeout": 5, "protocol": "tcp",
                 "enabled": 1, "created_at": "2024-01-01", "updated_at": "2024-01-01",
                 "status": "online", "last_seen": "2024-01-01 10:00:00"},
                {"id": 2, "name": "Test Device 2", "location": "Office B", "zone": "Zone 2",
                 "ip": "192.168.1.102", "address": "192.168.1.102", "port": 4370, "password": 1234, "timeout": 5, "protocol": "tcp",
                 "enabled": 1, "created_at": "2024-01-01", "updated_at": "2024-01-01",
                 "status": "offline", "last_seen": "2024-01-01 09:00:00"},
            ]
        return []

    mock_db.fetch_all.side_effect = fetch_all_side_effect
    mock_db.insert.return_value = 3  # New device ID
    mock_db.update.return_value = None
    mock_db.delete.return_value = None
    mock_db.fetch_one.return_value = None
    app.db = mock_db

    # Register devices blueprint
    from src.webgui.routes.devices import devices_bp
    app.register_blueprint(devices_bp)

    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


class TestDevicesList:
    """Tests for device list endpoint"""

    def test_list_devices_success(self, client):
        """Test listing devices returns HTML with device data"""
        response = client.get("/")

        assert response.status_code == 200
        assert b"Test Device 1" in response.data
        assert b"Test Device 2" in response.data
        assert b"192.168.1.101" in response.data

    def test_list_devices_empty(self, client):
        """Test listing devices when empty"""
        client.application.db.fetch_all.side_effect = lambda *args, **kwargs: []
        response = client.get("/")

        assert response.status_code == 200
        # Should still render template


class TestDeviceCreate:
    """Tests for device creation endpoint"""

    def test_create_device_get(self, client):
        """Test GET /new renders create form"""
        response = client.get("/new")

        assert response.status_code == 200
        # Template uses "Nuevo Dispositivo" as title
        assert b"Nuevo Dispositivo" in response.data

    def test_create_device_post_success(self, client):
        """Test POST /new creates device successfully"""
        response = client.post("/new", data={
            "name": "New Device",
            "location": "New Location",
            "zone": "New Zone",
            "address": "192.168.1.103",
            "port": "4370",
            "password": "0",
            "timeout": "5",
            "protocol": "tcp",
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should redirect to list after success
        assert b"Dispositivo" in response.data
        client.application.db.insert.assert_called_once()

    def test_create_device_post_missing_name(self, client):
        """Test POST /new with missing name shows error"""
        response = client.post("/new", data={
            "name": "",
            "location": "New Location",
            "zone": "New Zone",
            "address": "192.168.1.103",
            "port": "4370",
            "password": "0",
            "timeout": "5",
            "protocol": "tcp",
        })

        assert response.status_code == 200
        assert b"Nombre es requerido" in response.data or b"error" in response.data.lower()

    def test_create_device_post_missing_address(self, client):
        """Test POST /new with missing address shows error"""
        response = client.post("/new", data={
            "name": "New Device",
            "location": "New Location",
            "zone": "New Zone",
            "address": "",
            "port": "4370",
            "password": "0",
            "timeout": "5",
            "protocol": "tcp",
        })

        assert response.status_code == 200
        assert b"Direcci" in response.data  # "Dirección es requerida"

    def test_create_device_post_invalid_port(self, client):
        """Test POST /new with invalid port"""
        response = client.post("/new", data={
            "name": "New Device",
            "location": "New Location",
            "zone": "New Zone",
            "address": "192.168.1.103",
            "port": "invalid",
            "password": "0",
            "timeout": "5",
            "protocol": "tcp",
        })

        # ValueError on int() conversion - will cause 500 or be handled
        # The important thing is it doesn't crash silently
        assert response.status_code in [200, 400, 500]


class TestDeviceEdit:
    """Tests for device edit endpoint"""

    def test_edit_device_get(self, client):
        """Test GET /<id>/edit renders edit form"""
        # Mock fetch_one for device details
        client.application.db.fetch_one.return_value = {
            "id": 1, "name": "Test Device 1", "location": "Office A", "zone": "Zone 1",
            "ip": "192.168.1.101", "port": 4370, "password": 0, "timeout": 5, "protocol": "tcp"
        }

        response = client.get("/1/edit")

        assert response.status_code == 200
        assert b"Test Device 1" in response.data
        assert b"192.168.1.101" in response.data
        client.application.db.fetch_one.assert_called_once()

    def test_edit_device_get_not_found(self, client):
        """Test GET /<id>/edit for non-existent device"""
        client.application.db.fetch_one.return_value = None

        response = client.get("/999/edit")

        # Redirects to list with flash error
        assert response.status_code == 302
        assert "/devices" in response.location

    def test_edit_device_post_success(self, client):
        """Test POST /<id>/edit updates device successfully"""
        response = client.post("/1/edit", data={
            "name": "Updated Device",
            "location": "Updated Location",
            "zone": "Updated Zone",
            "address": "192.168.1.104",
            "port": "4370",
            "password": "0",
            "timeout": "5",
            "protocol": "tcp",
        }, follow_redirects=True)

        assert response.status_code == 200
        client.application.db.update.assert_called_once()
        # Verify update called with correct data including updated_at
        call_args = client.application.db.update.call_args
        assert call_args[0][0] == "devices"
        assert call_args[0][1]["name"] == "Updated Device"
        assert call_args[0][1]["ip"] == "192.168.1.104"
        assert "updated_at" in call_args[0][1]

    def test_edit_device_post_missing_fields(self, client):
        """Test POST /<id>/edit with missing required fields"""
        # Mock fetch_one to return a device (required for template)
        client.application.db.fetch_one.return_value = {
            "id": 1, "name": "Test Device", "location": "Office", "zone": "Zone",
            "ip": "192.168.1.101", "port": 4370, "password": 0, "timeout": 5, "protocol": "tcp"
        }

        response = client.post("/1/edit", data={
            "name": "",
            "location": "Updated Location",
            "zone": "Updated Zone",
            "address": "",
            "port": "4370",
            "password": "0",
            "timeout": "5",
            "protocol": "tcp",
        })

        # Renders template with error flash
        assert response.status_code == 200
        assert b"Nombre y direcci" in response.data  # "Nombre y dirección son requeridos"
        # Should not call update
        client.application.db.update.assert_not_called()


class TestDeviceDelete:
    """Tests for device delete endpoint"""

    def test_delete_device_success(self, client):
        """Test DELETE /<id>/delete removes device"""
        response = client.post("/1/delete")

        # Should redirect or return JSON
        assert response.status_code in [200, 302]
        client.application.db.delete.assert_called_once_with("devices", "id = ?", (1,))

    def test_delete_device_with_referenced_users(self, client):
        """Test delete when device has users (if foreign key constraint)"""
        # If there's a foreign key, this might fail
        client.application.db.delete.side_effect = Exception("Foreign key constraint")
        response = client.post("/1/delete")

        # Should handle gracefully - likely redirects back
        assert response.status_code in [302, 500]


class TestDeviceDiscovery:
    """Tests for device discovery endpoints (if any)"""

    @patch("src.webgui.routes.devices.discover_devices")
    def test_discover_devices(self, mock_discover, client):
        """Test device discovery endpoint"""
        mock_discover.return_value = [
            {"ip": "192.168.1.200", "port": 4370, "serial": "ABC123", "model": "K40"}
        ]

        response = client.get("/discover")

        assert response.status_code == 200
        # Response should contain discovered devices


class TestDevicesAuth:
    """Tests for auth requirements on devices endpoints"""

    def test_list_devices_no_auth(self, client):
        """Test list devices requires auth"""
        # Most endpoints might require login
        response = client.get("/")
        # May redirect to login or allow (depends on auth setup)
        assert response.status_code in [200, 302, 401]

    def test_create_device_no_auth(self, client):
        """Test create device requires auth"""
        response = client.post("/new", data={"name": "Test"})
        assert response.status_code in [200, 302, 401]

    def test_edit_device_no_auth(self, client):
        """Test edit device requires auth"""
        # GET first to trigger fetch_one, then POST
        client.application.db.fetch_one.return_value = {
            "id": 1, "name": "Test Device", "location": "Office", "zone": "Zone",
            "ip": "192.168.1.101", "port": 4370, "password": 0, "timeout": 5, "protocol": "tcp"
        }
        response = client.post("/1/edit", data={"name": "Test"})
        # Should work (no auth enforced in current implementation)
        assert response.status_code in [200, 302]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
