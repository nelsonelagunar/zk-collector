"""
Tests para el módulo ZK Client
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.zk.attendance import AttendanceRecord
from src.zk.client import ZKClient
from src.zk.exceptions import ZKConnectionError


class TestZKClient:
    """Tests para ZKClient"""

    def test_init(self):
        """Test de inicialización"""
        client = ZKClient('192.168.1.101', port=4370, timeout=5)

        assert client.ip == '192.168.1.101'
        assert client.port == 4370
        assert client.timeout == 5
        assert not client.connected

    def test_connect_success(self):
        """Test de conexión exitosa"""
        client = ZKClient('192.168.1.101')

        with patch('src.zk.client.ZK') as mock_zk:
            mock_instance = Mock()
            mock_zk.return_value = mock_instance

            result = client.connect()

            assert result
            assert client.connected
            mock_zk.assert_called_once()
            mock_instance.connect.assert_called_once()

    def test_connect_failure(self):
        """Test de fallo de conexión"""
        client = ZKClient('192.168.1.101')

        with patch('src.zk.client.ZK') as mock_zk:
            mock_zk.side_effect = Exception("Connection failed")

            with pytest.raises(ZKConnectionError):
                client.connect(max_retries=1)

    def test_disconnect(self):
        """Test de desconexión"""
        client = ZKClient('192.168.1.101')
        client.connected = True
        client.zk = Mock()

        client.disconnect()

        assert not client.connected
        assert client.zk is None

    def test_get_attendance(self):
        """Test de obtención de registros"""
        client = ZKClient('192.168.1.101')
        client.connected = True
        client.zk = Mock()

        # Mock de datos de asistencia
        mock_attendance = Mock()
        mock_attendance.user_id = "1"
        mock_attendance.timestamp = datetime.now()
        mock_attendance.status = 0

        client.zk.get_attendance.return_value = [mock_attendance]

        records = client.get_attendance()

        assert records is not None
        assert len(records) == 1
        assert isinstance(records[0], AttendanceRecord)

    def test_get_device_info(self):
        """Test de obtención de información del dispositivo"""
        client = ZKClient('192.168.1.101')
        client.connected = True
        client.zk = Mock()

        client.zk.get_firmware_version.return_value = "6.60"
        client.zk.get_serialnumber.return_value = "TEST123"

        info = client.get_device_info()

        assert info is not None
        assert info['firmware_version'] == "6.60"
        assert info['serial_number'] == "TEST123"


class TestAttendanceRecord:
    """Tests para AttendanceRecord"""

    def test_from_zk_attendance(self, sample_attendance_record):
        """Test de creación desde objeto pyzk"""
        record = AttendanceRecord.from_zk_attendance(
            sample_attendance_record,
            '192.168.1.101'
        )

        assert record.user_id == "1"
        assert record.device_ip == '192.168.1.101'
        assert record.punch_type == 'entrada'

    def test_punch_type_derivation(self):
        """Test de derivación de punch_type"""
        # Status 0 = entrada
        record = AttendanceRecord(
            user_id="1",
            timestamp=datetime.now(),
            status=0,
            device_ip="192.168.1.101"
        )
        assert record.punch_type == 'entrada'

        # Status 1 = salida
        record.status = 1
        # Necesitamos recrear porque punch_type se setea en __post_init__
        record2 = AttendanceRecord(
            user_id="1",
            timestamp=datetime.now(),
            status=1,
            device_ip="192.168.1.101"
        )
        assert record2.punch_type == 'salida'

    def test_to_dict(self):
        """Test de conversión a diccionario"""
        record = AttendanceRecord(
            user_id="1",
            timestamp=datetime(2026, 3, 3, 8, 0, 0),
            status=0,
            device_ip="192.168.1.101"
        )

        data = record.to_dict()

        assert data['user_id'] == "1"
        assert data['punch_type'] == 'entrada'
        assert '2026-03-03' in data['timestamp']
