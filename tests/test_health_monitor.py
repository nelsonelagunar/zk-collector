"""
Unit tests for HealthMonitor module
"""
import logging
import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.monitoring.health import HealthMonitor


@pytest.fixture
def mock_platform_sync():
    """Create mock PlatformSync"""
    return Mock()


class TestHealthMonitor:
    """Tests for HealthMonitor class"""

    def test_init(self, mock_platform_sync):
        """Test HealthMonitor initialization"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=600)

        assert monitor.platform_sync == mock_platform_sync
        assert monitor.interval == 600
        assert monitor.running is False
        assert monitor._thread is None
        assert monitor.devices_status == []
        assert monitor.last_metrics == {}

    def test_start(self, mock_platform_sync):
        """Test start() method"""
        with patch('src.monitoring.health.threading.Thread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
            monitor.start()

            assert monitor.running is True
            mock_thread_class.assert_called_once_with(target=monitor._run, daemon=True)
            mock_thread.start.assert_called_once()

    def test_start_already_running(self, mock_platform_sync):
        """Test start() when already running does nothing"""
        with patch('src.monitoring.health.threading.Thread') as mock_thread_class:
            monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
            monitor.running = True
            monitor._thread = Mock()

            monitor.start()
            mock_thread_class.assert_not_called()

    def test_stop(self, mock_platform_sync):
        """Test stop() method"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        mock_thread = Mock()
        monitor.running = True
        monitor._thread = mock_thread
        monitor._stop_event = Mock()

        monitor.stop()

        assert monitor.running is False
        monitor._stop_event.set.assert_called_once()
        mock_thread.join.assert_called_once_with(timeout=5)
        assert monitor._thread is None

    def test_stop_not_running(self, mock_platform_sync):
        """Test stop() when not running does nothing"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.running = False
        monitor._thread = None

        monitor.stop()  # Should not raise

    @patch('src.monitoring.health.psutil')
    def test_collect_metrics_success(self, mock_psutil, mock_platform_sync):
        """Test _collect_metrics() successful collection"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)

        # Setup psutil mocks
        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 8

        mock_memory = Mock()
        mock_memory.total = 16 * (1024 ** 3)
        mock_memory.available = 8 * (1024 ** 3)
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.total = 500 * (1024 ** 3)
        mock_disk.used = 200 * (1024 ** 3)
        mock_disk.free = 300 * (1024 ** 3)
        mock_disk.percent = 40.0
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.sensors_temperatures.return_value = {
            'cpu_thermal': [Mock(current=55.0)]
        }
        mock_psutil.boot_time.return_value = time.time() - 3600  # 1 hour ago

        metrics = monitor._collect_metrics()

        assert 'timestamp' in metrics
        assert metrics['cpu']['percent'] == 45.5
        assert metrics['cpu']['count'] == 8
        assert metrics['memory']['total'] == 16 * (1024 ** 3)
        assert metrics['memory']['available'] == 8 * (1024 ** 3)
        assert metrics['memory']['percent'] == 50.0
        assert metrics['disk']['total'] == 500 * (1024 ** 3)
        assert metrics['disk']['percent'] == 40.0
        assert metrics['temperature'] == 55.0
        assert metrics['uptime_seconds'] > 3500

    @patch('src.monitoring.health.psutil')
    def test_collect_metrics_no_temperature(self, mock_psutil, mock_platform_sync):
        """Test _collect_metrics() when temperature sensors not available"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)

        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 4

        mock_memory = Mock()
        mock_memory.total = 8 * (1024 ** 3)
        mock_memory.available = 4 * (1024 ** 3)
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.total = 250 * (1024 ** 3)
        mock_disk.used = 100 * (1024 ** 3)
        mock_disk.free = 150 * (1024 ** 3)
        mock_disk.percent = 40.0
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.sensors_temperatures.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 7200

        metrics = monitor._collect_metrics()

        assert metrics['temperature'] is None

    @patch('src.monitoring.health.psutil')
    def test_collect_metrics_raspberry_pi_temp(self, mock_psutil, mock_platform_sync):
        """Test _collect_metrics() Raspberry Pi temperature"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)

        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 4

        mock_memory = Mock()
        mock_memory.total = 8 * (1024 ** 3)
        mock_memory.available = 4 * (1024 ** 3)
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.total = 250 * (1024 ** 3)
        mock_disk.used = 100 * (1024 ** 3)
        mock_disk.free = 150 * (1024 ** 3)
        mock_disk.percent = 40.0
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.sensors_temperatures.return_value = {
            'bcm2835_thermal': [Mock(current=65.0)]
        }
        mock_psutil.boot_time.return_value = time.time() - 7200

        metrics = monitor._collect_metrics()

        assert metrics['temperature'] == 65.0

    @patch('src.monitoring.health.psutil')
    def test_collect_metrics_exception_handling(self, mock_psutil, mock_platform_sync, caplog):
        """Test _collect_metrics() handles exceptions"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        mock_psutil.cpu_percent.side_effect = Exception("psutil error")

        metrics = monitor._collect_metrics()

        assert 'error' in metrics
        assert metrics['error'] == 'psutil error'
        assert 'timestamp' in metrics
        assert "Error recopilando métricas" in caplog.text

    def test_update_device_status(self, mock_platform_sync):
        """Test update_device_status()"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        devices = [
            {'ip': '192.168.1.100', 'connected': True},
            {'ip': '192.168.1.101', 'connected': False}
        ]
        monitor.update_device_status(devices)

        assert monitor.devices_status == devices

    def test_get_current_metrics(self, mock_platform_sync):
        """Test get_current_metrics() returns a shallow copy"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {'cpu': {'percent': 50}}

        metrics = monitor.get_current_metrics()

        assert metrics == {'cpu': {'percent': 50}}
        # Returns shallow copy - nested dicts are shared
        # This is the actual behavior of dict.copy()
        metrics['cpu']['percent'] = 100
        assert monitor.last_metrics['cpu']['percent'] == 100

    def test_get_system_health_healthy(self, mock_platform_sync):
        """Test get_system_health() when system is healthy"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 50
        }
        monitor.devices_status = [
            {'connected': True},
            {'connected': True},
            {'connected': False}
        ]

        health = monitor.get_system_health()

        assert health['status'] == 'healthy'
        assert health['issues'] == []
        assert health['devices_count'] == 3
        assert health['devices_online'] == 2

    def test_get_system_health_cpu_warning(self, mock_platform_sync):
        """Test get_system_health() with high CPU"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 95},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 50
        }
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'warning'
        assert 'CPU usage high' in health['issues']

    def test_get_system_health_memory_warning(self, mock_platform_sync):
        """Test get_system_health() with high memory"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 95},
            'disk': {'percent': 50},
            'temperature': 50
        }
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'warning'
        assert 'Memory usage high' in health['issues']

    def test_get_system_health_disk_critical(self, mock_platform_sync):
        """Test get_system_health() with critical disk"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 95},
            'temperature': 50
        }
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'critical'
        assert 'Disk usage critical' in health['issues']

    def test_get_system_health_temperature_critical(self, mock_platform_sync):
        """Test get_system_health() with critical temperature"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 85
        }
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'critical'
        assert 'Temperature critical' in health['issues']

    def test_get_system_health_temperature_warning(self, mock_platform_sync):
        """Test get_system_health() with high temperature"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': 75
        }
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'warning'
        assert 'Temperature high' in health['issues']

    def test_get_system_health_no_temperature(self, mock_platform_sync):
        """Test get_system_health() with no temperature data"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {
            'cpu': {'percent': 50},
            'memory': {'percent': 50},
            'disk': {'percent': 50},
            'temperature': None
        }
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'healthy'
        assert health['issues'] == []

    def test_get_system_health_missing_metrics(self, mock_platform_sync):
        """Test get_system_health() with missing metrics"""
        monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=300)
        monitor.last_metrics = {}
        monitor.devices_status = []

        health = monitor.get_system_health()

        assert health['status'] == 'healthy'
        assert health['issues'] == []


class TestHealthMonitorRunLoop:
    """Tests for HealthMonitor run loop"""

    @patch('src.monitoring.health.psutil')
    def test_run_loop_sends_heartbeat(self, mock_psutil, mock_platform_sync):
        """Test _run() loop sends heartbeat"""
        health_monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=1)

        # Setup psutil mocks
        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 4

        mock_memory = Mock()
        mock_memory.total = 8 * (1024 ** 3)
        mock_memory.available = 4 * (1024 ** 3)
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.total = 250 * (1024 ** 3)
        mock_disk.used = 100 * (1024 ** 3)
        mock_disk.free = 150 * (1024 ** 3)
        mock_disk.percent = 40.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.sensors_temperatures.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 3600

        mock_platform_sync.send_heartbeat.return_value = True

        # Run one iteration manually
        health_monitor.running = True
        health_monitor._stop_event = Mock()
        health_monitor._stop_event.wait.return_value = None
        health_monitor._stop_event.is_set.side_effect = [False, True]  # Run once, then stop

        health_monitor._run()

        # Verify heartbeat was sent
        mock_platform_sync.send_heartbeat.assert_called_once()
        call_args = mock_platform_sync.send_heartbeat.call_args
        assert 'metrics' in call_args[1]
        assert 'devices_status' in call_args[1]

    @patch('src.monitoring.health.psutil')
    def test_run_loop_handles_heartbeat_failure(self, mock_psutil, mock_platform_sync, caplog):
        """Test _run() handles heartbeat failure"""
        health_monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=1)

        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(total=8e9, available=4e9, percent=50)
        mock_psutil.disk_usage.return_value = Mock(total=250e9, used=100e9, free=150e9, percent=40)
        mock_psutil.sensors_temperatures.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 3600

        mock_platform_sync.send_heartbeat.return_value = False

        health_monitor.running = True
        health_monitor._stop_event = Mock()
        health_monitor._stop_event.wait.return_value = None
        health_monitor._stop_event.is_set.side_effect = [False, True]

        with caplog.at_level(logging.WARNING):
            health_monitor._run()

        assert "Error enviando heartbeat" in caplog.text

    @patch('src.monitoring.health.psutil')
    def test_run_loop_handles_exception(self, mock_psutil, mock_platform_sync, caplog):
        """Test _run() handles exceptions in loop"""
        health_monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=1)

        # Exception in psutil.cpu_percent is caught in _collect_metrics
        # and logged as "Error recopilando métricas"
        mock_psutil.cpu_percent.side_effect = Exception("Collection error")

        health_monitor.running = True
        health_monitor._stop_event = Mock()
        health_monitor._stop_event.wait.return_value = None
        health_monitor._stop_event.is_set.side_effect = [False, True]

        with caplog.at_level(logging.ERROR):
            health_monitor._run()

        # The exception is caught in _collect_metrics
        assert "Error recopilando métricas" in caplog.text

    @patch('src.monitoring.health.threading.Thread')
    @patch('src.monitoring.health.psutil')
    def test_start_stop_integration(self, mock_psutil, mock_thread_class, mock_platform_sync):
        """Test start/stop integration"""
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(total=8e9, available=4e9, percent=50)
        mock_psutil.disk_usage.return_value = Mock(total=250e9, used=100e9, free=150e9, percent=40)
        mock_psutil.sensors_temperatures.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 3600

        health_monitor = HealthMonitor(platform_sync=mock_platform_sync, interval=1)
        health_monitor.start()

        assert health_monitor.running is True
        mock_thread.start.assert_called_once()

        health_monitor.stop()

        assert health_monitor.running is False
        mock_thread.join.assert_called_once_with(timeout=5)