"""
Unit tests for HealthMonitor
"""

from unittest.mock import Mock, patch

import pytest

from src.monitoring.health import HealthMonitor
from src.sync.platform import PlatformSync


class TestHealthMonitor:
    """Tests for HealthMonitor"""

    @pytest.fixture
    def mock_platform_sync(self):
        return Mock(spec=PlatformSync)

    @pytest.fixture
    def health_monitor(self, mock_platform_sync):
        return HealthMonitor(platform_sync=mock_platform_sync, interval=300)

    def test_init(self, health_monitor, mock_platform_sync):
        """Test initialization"""
        assert health_monitor.platform_sync == mock_platform_sync
        assert health_monitor.interval == 300
        assert health_monitor.running is False
        assert health_monitor._thread is None
        assert health_monitor.devices_status == []
        assert health_monitor.last_metrics == {}

    def test_start_stop(self, health_monitor):
        """Test start and stop"""
        health_monitor.start()
        assert health_monitor.running is True
        assert health_monitor._thread is not None

        health_monitor.stop()
        assert health_monitor.running is False

    def test_update_device_status(self, health_monitor):
        """Test updating device status"""
        devices = [
            {'ip': '192.168.1.101', 'connected': True},
            {'ip': '192.168.1.102', 'connected': False}
        ]
        health_monitor.update_device_status(devices)
        assert health_monitor.devices_status == devices

    def test_get_current_metrics(self, health_monitor):
        """Test getting current metrics"""
        health_monitor.last_metrics = {'cpu': {'percent': 50}}
        metrics = health_monitor.get_current_metrics()
        assert metrics == {'cpu': {'percent': 50}}
        # Should return copy
        assert metrics is not health_monitor.last_metrics

    @patch('src.monitoring.health.psutil.cpu_percent')
    @patch('src.monitoring.health.psutil.cpu_count')
    @patch('src.monitoring.health.psutil.virtual_memory')
    @patch('src.monitoring.health.psutil.disk_usage')
    @patch('src.monitoring.health.psutil.boot_time')
    @patch('src.monitoring.health.time.time')
    def test_collect_metrics(
        self,
        mock_time,
        mock_boot_time,
        mock_disk_usage,
        mock_virtual_memory,
        mock_cpu_count,
        mock_cpu_percent,
        health_monitor,
    ):
        """Test collecting metrics"""
        mock_cpu_percent.return_value = 45.0
        mock_cpu_count.return_value = 4
        mock_virtual_memory.return_value = Mock(
            total=8000000000, available=4000000000, percent=50.0
        )
        mock_disk_usage.return_value = Mock(
            total=100000000000,
            used=50000000000,
            free=50000000000,
            percent=50.0,
        )
        mock_boot_time.return_value = 1000000
        mock_time.return_value = 2000000

        metrics = health_monitor._collect_metrics()

        assert 'timestamp' in metrics
        assert metrics['cpu']['percent'] == 45.0
        assert metrics['cpu']['count'] == 4
        assert metrics['memory']['total'] == 8000000000
        assert metrics['memory']['percent'] == 50.0
        assert metrics['disk']['percent'] == 50.0
        assert metrics['uptime_seconds'] == 1000000

    @patch('src.monitoring.health.psutil.sensors_temperatures')
    @patch('src.monitoring.health.psutil.cpu_percent')
    @patch('src.monitoring.health.psutil.cpu_count')
    @patch('src.monitoring.health.psutil.virtual_memory')
    @patch('src.monitoring.health.psutil.disk_usage')
    @patch('src.monitoring.health.psutil.boot_time')
    @patch('src.monitoring.health.time.time')
    def test_collect_metrics_with_temperature(
        self,
        mock_time,
        mock_boot_time,
        mock_disk_usage,
        mock_virtual_memory,
        mock_cpu_count,
        mock_cpu_percent,
        mock_sensors_temperatures,
        health_monitor,
    ):
        """Test collecting metrics with temperature"""
        mock_cpu_percent.return_value = 45.0
        mock_cpu_count.return_value = 4
        mock_virtual_memory.return_value = Mock(
            total=8000000000, available=4000000000, percent=50.0
        )
        mock_disk_usage.return_value = Mock(
            total=100000000000,
            used=50000000000,
            free=50000000000,
            percent=50.0,
        )
        mock_boot_time.return_value = 1000000
        mock_time.return_value = 2000000
        mock_sensors_temperatures.return_value = {'cpu_thermal': [Mock(current=55.0)]}

        metrics = health_monitor._collect_metrics()

        assert metrics['temperature'] == 55.0

    @patch('src.monitoring.health.psutil.sensors_temperatures')
    @patch('src.monitoring.health.psutil.cpu_percent')
    @patch('src.monitoring.health.psutil.cpu_count')
    @patch('src.monitoring.health.psutil.virtual_memory')
    @patch('src.monitoring.health.psutil.disk_usage')
    @patch('src.monitoring.health.psutil.boot_time')
    @patch('src.monitoring.health.time.time')
    def test_collect_metrics_with_rpi_temperature(
        self,
        mock_time,
        mock_boot_time,
        mock_disk_usage,
        mock_virtual_memory,
        mock_cpu_count,
        mock_cpu_percent,
        mock_sensors_temperatures,
        health_monitor,
    ):
        """Test collecting metrics with Raspberry Pi temperature"""
        mock_cpu_percent.return_value = 45.0
        mock_cpu_count.return_value = 4
        mock_virtual_memory.return_value = Mock(
            total=8000000000, available=4000000000, percent=50.0
        )
        mock_disk_usage.return_value = Mock(
            total=100000000000,
            used=50000000000,
            free=50000000000,
            percent=50.0,
        )
        mock_boot_time.return_value = 1000000
        mock_time.return_value = 2000000
        mock_sensors_temperatures.return_value = {'bcm2835_thermal': [Mock(current=60.0)]}

        metrics = health_monitor._collect_metrics()

        assert metrics['temperature'] == 60.0

    def test_get_system_health_healthy(self, health_monitor):
        """Test system health when healthy"""
        health_monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 40
        }
        health_monitor.devices_status = [
            {'connected': True},
            {'connected': True}
        ]

        health = health_monitor.get_system_health()

        assert health['status'] == 'healthy'
        assert health['issues'] == []
        assert health['devices_count'] == 2
        assert health['devices_online'] == 2

    def test_get_system_health_cpu_warning(self, health_monitor):
        """Test system health with high CPU"""
        health_monitor.last_metrics = {
            'cpu': {'percent': 95},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
        }
        health_monitor.devices_status = []

        health = health_monitor.get_system_health()

        assert health['status'] == 'warning'
        assert 'CPU usage high' in health['issues']

    def test_get_system_health_memory_warning(self, health_monitor):
        """Test system health with high memory"""
        health_monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 95},
            'disk': {'percent': 50},
        }

        health = health_monitor.get_system_health()

        assert health['status'] == 'warning'
        assert 'Memory usage high' in health['issues']

    def test_get_system_health_disk_critical(self, health_monitor):
        """Test system health with critical disk"""
        health_monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 95},
        }

        health = health_monitor.get_system_health()

        assert health['status'] == 'critical'
        assert 'Disk usage critical' in health['issues']

    def test_get_system_health_temperature_critical(self, health_monitor):
        """Test system health with critical temperature"""
        health_monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 85
        }

        health = health_monitor.get_system_health()

        assert health['status'] == 'critical'
        assert 'Temperature critical' in health['issues']

    def test_get_system_health_temperature_warning(self, health_monitor):
        """Test system health with high temperature"""
        health_monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 75
        }

        health = health_monitor.get_system_health()

        assert health['status'] == 'warning'
        assert 'Temperature high' in health['issues']
