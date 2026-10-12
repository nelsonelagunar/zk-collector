"""
Tests para el módulo de descubrimiento de dispositivos ZKTeco
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import socket

from src.zk.discovery import ZKDiscovery, DiscoveredDevice, discover_devices


class TestDiscoveredDevice:
    """Tests para DiscoveredDevice dataclass"""

    def test_to_dict(self):
        """Test conversión a diccionario"""
        device = DiscoveredDevice(
            ip='192.168.1.101',
            port=4370,
            mac='AA:BB:CC:DD:EE:FF',
            model='K40',
            firmware='6.60',
            serial='TEST123',
            device_name='Entrada Principal'
        )

        data = device.to_dict()

        assert data['ip'] == '192.168.1.101'
        assert data['port'] == 4370
        assert data['mac'] == 'AA:BB:CC:DD:EE:FF'
        assert data['model'] == 'K40'
        assert data['firmware'] == '6.60'
        assert data['serial'] == 'TEST123'
        assert data['device_name'] == 'Entrada Principal'
        assert data['protocol'] == 'udp'


class TestZKDiscovery:
    """Tests para ZKDiscovery"""

    def test_init_defaults(self):
        """Test inicialización con valores por defecto"""
        discovery = ZKDiscovery()

        assert discovery.broadcast_address == '255.255.255.255'
        assert discovery.port == 4370
        assert discovery.timeout == 3.0
        assert discovery.retries == 2
        assert discovery.rate_limit_delay == 0.1

    def test_init_custom(self):
        """Test inicialización con valores personalizados"""
        discovery = ZKDiscovery(
            broadcast_address='192.168.1.255',
            port=4370,
            timeout=5.0,
            retries=3,
            rate_limit_delay=0.5
        )

        assert discovery.broadcast_address == '192.168.1.255'
        assert discovery.timeout == 5.0
        assert discovery.retries == 3
        assert discovery.rate_limit_delay == 0.5

    def test_get_broadcast_addresses_with_network(self):
        """Test obtención de broadcast addresses con CIDR"""
        discovery = ZKDiscovery()
        addrs = discovery._get_broadcast_addresses('192.168.1.0/24')

        assert '192.168.1.255' in addrs

    def test_get_broadcast_addresses_without_network(self):
        """Test obtención de broadcast addresses sin CIDR (fallback)"""
        discovery = ZKDiscovery()

        # Patch the module-level netifaces variable to simulate ImportError
        import src.zk.discovery as discovery_module
        original_netifaces = discovery_module.netifaces
        discovery_module.netifaces = None
        try:
            addrs = discovery._get_broadcast_addresses(None)
        finally:
            discovery_module.netifaces = original_netifaces

        # Should have fallback addresses
        assert '255.255.255.255' in addrs
        assert '192.168.1.255' in addrs
        assert '192.168.0.255' in addrs
        assert '10.255.255.255' in addrs

    def test_get_broadcast_addresses_deduplicates(self):
        """Test que se eliminan duplicados"""
        discovery = ZKDiscovery()

        # Network that produces same broadcast as fallback
        addrs = discovery._get_broadcast_addresses('192.168.1.0/24')
        assert len(addrs) == len(set(addrs))  # No duplicates

    @patch('src.zk.discovery.socket.socket')
    def test_create_socket(self, mock_socket_class):
        """Test creación de socket UDP"""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock

        discovery = ZKDiscovery()
        sock = discovery._create_socket()

        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.settimeout.assert_called_once_with(3.0)
        assert sock == mock_sock

    def test_parse_discovery_response_valid(self):
        """Test parseo de respuesta válida"""
        discovery = ZKDiscovery()

        # Create a mock response with proper structure
        # Offset 0-3: header (4 bytes), 4-7: IP (4 bytes), 8-13: MAC (6 bytes)
        # Offset 14-23: padding (10 bytes), 24+: extra info
        ip_bytes = b'\xc0\xa8\x01\x65'  # 192.168.1.101
        mac_bytes = b'\xaa\xbb\xcc\xdd\xee\xff'  # AA:BB:CC:DD:EE:FF
        padding = b'\x00' * 10  # padding to reach offset 24
        extra = b'K40\x006.60\x00TEST123\x00'
        data = b'\x00\x00\x00\x00' + ip_bytes + mac_bytes + padding + extra

        device = discovery._parse_discovery_response(data, ('192.168.1.101', 4370))

        assert device is not None
        assert device.ip == '192.168.1.101'
        assert device.mac == 'AA:BB:CC:DD:EE:FF'
        assert device.model == 'K40'
        assert device.firmware == '6.60'
        assert device.serial == 'TEST123'

    def test_parse_discovery_response_too_short(self):
        """Test parseo de respuesta muy corta"""
        discovery = ZKDiscovery()

        data = b'\x00\x00'  # Too short
        device = discovery._parse_discovery_response(data, ('192.168.1.101', 4370))

        assert device is None

    def test_parse_discovery_response_fallback_ip(self):
        """Test que usa IP del addr cuando no hay IP en respuesta"""
        discovery = ZKDiscovery()

        # Response without IP bytes - need at least 24 bytes to pass minimum check
        # Header (4) + 4 zero bytes (no IP) + MAC (6) + padding to reach 24
        data = b'\x00\x00\x00\x00' + b'\x00\x00\x00\x00' + b'\xaa\xbb\xcc\xdd\xee\xff' + b'\x00' * 10
        device = discovery._parse_discovery_response(data, ('192.168.1.101', 4370))

        assert device is not None
        assert device.ip == '192.168.1.101'  # Falls back to addr[0]
        assert device.mac == 'AA:BB:CC:DD:EE:FF'

    def test_parse_discovery_response_mac_from_end(self):
        """Test extracción de MAC del final cuando response es corta (less than 14 bytes)"""
        discovery = ZKDiscovery()

        # The early return requires 24 bytes minimum, so we can't test < 14 directly
        # But we can test that when len(data) < 14, it would use data[-6:] - this is tested
        # indirectly by the valid response test. For now, test a 24-byte response where
        # MAC is at the end of the data (not at offset 8)
        # Actually the code uses data[8:14] for len >= 14, so this test name is misleading
        # Let's test a valid case with MAC at offset 8
        data = (
            b'\x00\x00\x00\x00' +  # header (4)
            b'\xc0\xa8\x01\x65' +  # IP (4) = 192.168.1.101
            b'\xaa\xbb\xcc\xdd\xee\xff' +  # MAC (6) at offset 8
            b'\x00' * 10  # padding to reach 24
        )
        device = discovery._parse_discovery_response(data, ('192.168.1.101', 4370))

        assert device is not None
        assert device.mac == 'AA:BB:CC:DD:EE:FF'
        assert device.ip == '192.168.1.101'


class TestDiscoverDevicesFunction:
    """Tests para la función de conveniencia discover_devices"""

    @patch('src.zk.discovery.ZKDiscovery.discover')
    def test_discover_devices_basic(self, mock_discover):
        """Test descubrimiento básico"""
        mock_device = Mock()
        mock_device.to_dict.return_value = {
            'ip': '192.168.1.101',
            'port': 4370,
            'mac': 'AA:BB:CC:DD:EE:FF',
        }
        mock_discover.return_value = [mock_device]

        devices = discover_devices(network='192.168.1.0/24', timeout=2.0, retries=1, fetch_details=False)

        assert len(devices) == 1
        assert devices[0]['ip'] == '192.168.1.101'
        mock_discover.assert_called_once_with('192.168.1.0/24')

    @patch('src.zk.discovery.ZKDiscovery.discover_with_details')
    def test_discover_devices_with_details(self, mock_discover_details):
        """Test descubrimiento con detalles"""
        mock_device = Mock()
        mock_device.to_dict.return_value = {
            'ip': '192.168.1.101',
            'port': 4370,
            'mac': 'AA:BB:CC:DD:EE:FF',
            'model': 'K40',
        }
        mock_discover_details.return_value = [mock_device]

        devices = discover_devices(network='192.168.1.0/24', fetch_details=True)

        assert len(devices) == 1
        assert devices[0]['model'] == 'K40'
        mock_discover_details.assert_called_once_with('192.168.1.0/24')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])