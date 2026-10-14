"""
Integration tests for WebGUI device CRUD and poll integration
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.webgui.database import Database
from src.webgui.routes.devices import devices_bp
from src.zk.client import ZKClient


class TestWebGUIDeviceCRUD:
    """Integration tests for WebGUI device CRUD operations"""

    @pytest.fixture
    def temp_db(self):
        """Temporary database"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def db(self, temp_db):
        """Database instance with initialized tables"""
        db = Database(temp_db)
        # Create tables manually for tests
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    location TEXT,
                    zone TEXT,
                    address TEXT NOT NULL,
                    port INTEGER DEFAULT 4370,
                    password INTEGER DEFAULT 0,
                    timeout INTEGER DEFAULT 5,
                    protocol TEXT DEFAULT 'tcp',
                    is_enabled INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'unknown',
                    firmware_version TEXT,
                    serial_number TEXT,
                    device_name TEXT,
                    mac_address TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        return db

    def test_create_device(self, db):
        """Test creating a device"""
        device_data = {
            'name': 'Test Device',
            'location': 'Main Entrance',
            'zone': 'Zone A',
            'address': '192.168.1.101',
            'port': 4370,
            'password': 0,
            'timeout': 5,
            'protocol': 'tcp',
        }

        device_id = db.insert('devices', device_data)
        assert device_id is not None
        assert device_id > 0

        # Verify device was created
        device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        assert device is not None
        assert device['name'] == 'Test Device'
        assert device['address'] == '192.168.1.101'
        assert device['port'] == 4370

    def test_list_devices(self, db):
        """Test listing devices"""
        # Create multiple devices
        for i in range(3):
            db.insert('devices', {
                'name': f'Device {i}',
                'address': f'192.168.1.{100+i}',
                'port': 4370,
            })

        devices = db.fetch_all("SELECT * FROM devices ORDER BY name")
        assert len(devices) == 3
        assert devices[0]['name'] == 'Device 0'

    def test_update_device(self, db):
        """Test updating a device"""
        device_id = db.insert('devices', {
            'name': 'Original',
            'address': '192.168.1.101',
        })

        # Update
        db.update('devices', {'name': 'Updated', 'port': 4371}, 'id = ?', (device_id,))

        device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        assert device['name'] == 'Updated'
        assert device['port'] == 4371

    def test_delete_device(self, db):
        """Test deleting a device"""
        device_id = db.insert('devices', {
            'name': 'To Delete',
            'address': '192.168.1.101',
        })

        db.delete('devices', 'id = ?', (device_id,))

        device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        assert device is None

    def test_toggle_device_enabled(self, db):
        """Test toggling device enabled state"""
        device_id = db.insert('devices', {
            'name': 'Test',
            'address': '192.168.1.101',
            'is_enabled': 1
        })

        # Toggle to disabled
        db.update('devices', {'is_enabled': 0}, 'id = ?', (device_id,))
        device = db.fetch_one("SELECT is_enabled FROM devices WHERE id = ?", (device_id,))
        assert device['is_enabled'] == 0

        # Toggle to enabled
        db.update('devices', {'is_enabled': 1}, 'id = ?', (device_id,))
        device = db.fetch_one("SELECT is_enabled FROM devices WHERE id = ?", (device_id,))
        assert device['is_enabled'] == 1


class TestWebGUIPollIntegration:
    """Integration tests for WebGUI device test connection and polling"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def db(self, temp_db):
        db = Database(temp_db)
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    location TEXT,
                    zone TEXT,
                    address TEXT NOT NULL,
                    port INTEGER DEFAULT 4370,
                    password INTEGER DEFAULT 0,
                    timeout INTEGER DEFAULT 5,
                    protocol TEXT DEFAULT 'tcp',
                    is_enabled INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'unknown',
                    firmware_version TEXT,
                    serial_number TEXT,
                    device_name TEXT,
                    mac_address TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        return db

    @pytest.mark.asyncio
    async def test_device_test_connection_success(self, db):
        """Test device connection test endpoint with emulator"""
        from tests.integration.test_emulator_integration import _handle_client

        server = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port = server.sockets[0].getsockname()[1]

        try:
            # Create device in DB
            device_id = db.insert('devices', {
                'name': 'Emulator Device',
                'address': '127.0.0.1',
                'port': port,
                'password': 0,
                'timeout': 5,
                'protocol': 'tcp',
            })

            # Test connection using ZKClient
            client = ZKClient('127.0.0.1', port=port, timeout=5)

            with patch('src.zk.client.ZK') as mock_zk:
                mock_instance = Mock()
                mock_zk.return_value = mock_instance
                mock_instance.connect.return_value = True
                mock_instance.get_firmware_version.return_value = '6.60'
                mock_instance.get_serialnumber.return_value = 'EMU123456'
                mock_instance.get_platform.return_value = 'ZKEmulator'

                connected = client.connect(max_retries=1)
                assert connected

                info = client.get_device_info()
                assert info is not None
                assert info['firmware_version'] == '6.60'
                assert info['serial_number'] == 'EMU123456'

                # Update device status in DB
                db.update('devices', {
                    'status': 'online',
                    'firmware_version': info['firmware_version'],
                    'serial_number': info['serial_number'],
                }, 'id = ?', (device_id,))

                device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
                assert device['status'] == 'online'
                assert device['firmware_version'] == '6.60'

                client.disconnect()

        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_device_test_connection_failure(self, db):
        """Test device connection test with unreachable device"""
        # Create device with unreachable IP
        device_id = db.insert('devices', {
            'name': 'Unreachable',
            'address': '192.168.255.255',  # Unreachable IP
            'port': 4370,
        })

        client = ZKClient('192.168.255.255', port=4370, timeout=1)

        with patch('src.zk.client.ZK') as mock_zk:
            mock_zk.side_effect = ConnectionRefusedError("Connection refused")

            from src.zk.exceptions import ZKConnectionError
            with pytest.raises(ZKConnectionError):
                client.connect(max_retries=1)

            # Update device status to offline
            db.update('devices', {'status': 'offline'}, 'id = ?', (device_id,))
            device = db.fetch_one("SELECT status FROM devices WHERE id = ?", (device_id,))
            assert device['status'] == 'offline'

    @pytest.mark.asyncio
    async def test_full_device_flow_crud_to_poll(self, db):
        """Test full flow: create device -> test connection -> poll attendance"""
        from tests.integration.test_emulator_integration import _handle_client

        server = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port = server.sockets[0].getsockname()[1]

        try:
            # 1. CREATE device
            device_id = db.insert('devices', {
                'name': 'Integration Test Device',
                'location': 'Office',
                'zone': 'Zone 1',
                'address': '127.0.0.1',
                'port': port,
                'password': 0,
                'timeout': 5,
                'protocol': 'tcp',
                'is_enabled': 1,
            })

            # 2. TEST connection
            client = ZKClient('127.0.0.1', port=port, timeout=5)

            with patch('src.zk.client.ZK') as mock_zk:
                mock_instance = Mock()
                mock_zk.return_value = mock_instance
                mock_instance.connect.return_value = True
                mock_instance.get_firmware_version.return_value = '6.60'
                mock_instance.get_serialnumber.return_value = 'EMU123456'
                mock_instance.get_platform.return_value = 'ZKEmulator'
                mock_instance.get_device_name.return_value = 'ZKTeco Emulator'
                mock_instance.get_mac.return_value = '00:11:22:33:44:55'

                connected = client.connect(max_retries=1)
                assert connected

                info = client.get_device_info()
                assert info is not None

                # Update DB with device info
                db.update('devices', {
                    'status': 'online',
                    'firmware_version': info['firmware_version'],
                    'serial_number': info['serial_number'],
                    'device_name': info['device_name'],
                    'mac_address': info['mac_address'],
                }, 'id = ?', (device_id,))

                client.disconnect()

            # 3. VERIFY device in DB
            device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
            assert device['status'] == 'online'
            assert device['firmware_version'] == '6.60'
            assert device['is_enabled'] == 1

            # 4. POLL attendance (mocked)
            with patch('src.zk.client.ZK') as mock_zk:
                mock_instance = Mock()
                mock_zk.return_value = mock_instance
                mock_instance.connect.return_value = True
                mock_instance.get_attendance.return_value = []

                client2 = ZKClient('127.0.0.1', port=port, timeout=5)
                connected = client2.connect(max_retries=1)
                assert connected

                records = client2.get_attendance()
                assert records == []

                client2.disconnect()

            # 5. DISABLE device
            db.update('devices', {'is_enabled': 0}, 'id = ?', (device_id,))
            device = db.fetch_one("SELECT is_enabled FROM devices WHERE id = ?", (device_id,))
            assert device['is_enabled'] == 0

        finally:
            server.close()
            await server.wait_closed()


class TestWebGUIAPIEndpoints:
    """Test WebGUI API endpoints"""

    def test_api_test_device_endpoint(self):
        """Test the /api/devices/test endpoint"""
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(devices_bp)
        app.config['TESTING'] = True

        with app.test_client() as client, app.app_context():
            # Mock the database
            mock_db = Mock()
            mock_db.fetch_one.return_value = {
                'id': 1,
                'address': '192.168.1.101',
                'port': 4370,
                'timeout': 5,
                'password': 0,
                'protocol': 'tcp',
            }

            with patch('src.webgui.routes.devices.current_app') as mock_current_app:
                mock_current_app.db = mock_db

                with patch('src.webgui.routes.devices.ZK') as mock_zk:
                    mock_instance = Mock()
                    mock_zk.return_value = mock_instance
                    mock_instance.connect.return_value = True
                    mock_instance.get_firmware_version.return_value = '6.60'
                    mock_instance.get_serialnumber.return_value = 'TEST123'
                    mock_instance.get_platform.return_value = 'ZKTeco'

                    # Test the endpoint
                    response = client.post('/api/devices/test',
                        json={
                            'address': '192.168.1.101',
                            'port': 4370,
                            'timeout': 5,
                            'password': 0,
                            'protocol': 'tcp'
                        })

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    assert 'device_info' in data
                    assert data['device_info']['firmware'] == '6.60'

    def test_api_test_device_endpoint_failure(self):
        """Test API endpoint with connection failure"""
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(devices_bp)
        app.config['TESTING'] = True

        with app.test_client() as client, app.app_context(), \
             patch('src.webgui.routes.devices.ZK') as mock_zk:
            mock_zk.side_effect = Exception("Connection refused")

            response = client.post('/api/devices/test',
                json={
                    'address': '192.168.1.101',
                    'port': 4370,
                })

            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'Error' in data['message']
