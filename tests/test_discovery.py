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

        with patch('src.zk.discovery.netifaces', side_effect=ImportError):
            addrs = discovery._get_broadcast_addresses(None)

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
        # Offset 0-3: header, 4-7: IP (192.168.1.101), 8-13: MAC
        ip_bytes = b'\xc0\xa8\x01\x65'  # 192.168.1.101
        mac_bytes = b'\xaa\xbb\xcc\xdd\xee\xff'  # AA:BB:CC:DD:EE:FF
        data = b'\x00\x00\x00\x00' + ip_bytes + mac_bytes + b'K40\x006.60\x00TEST123\x00'

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

        # Response without IP bytes (less than 8 bytes for IP)
        data = b'\x00\x00\x00\x00\x00\x00' + b'\xaa\xbb\xcc\xdd\xee\xff'
        device = discovery._parse_discovery_response(data, ('192.168.1.101', 4370))

        assert device is not None
        assert device.ip == '192.168.1.101'  # Falls back to addr[0]

    def test_parse_discovery_response_mac_from_end(self):
        """Test extracción de MAC del final cuando response es corta"""
        discovery = ZKDiscovery()

        # Short response - MAC should come from last 6 bytes
        data = b'\x00\x00\x00\x00\x00\x00\x00\x00\xaa\xbb\xcc\xdd\xee\xff'
        device = discovery._parse_discovery_response(data, ('192.168.1.101', 4370))

        assert device is not None
        assert device.mac == 'AA:BB:CC:DD:EE:FF'


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