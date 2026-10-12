"""
Unit tests for HealthMonitor module
"""

import time
from unittest.mock import Mock, patch

import pytest

from src.monitoring.health import HealthMonitor


@pytest.fixture
def mock_platform_sync():
    """Mock PlatformSync"""
    sync = Mock()
    sync.send_heartbeat.return_value = True
    return sync


@pytest.fixture
def health_monitor(mock_platform_sync):
    """HealthMonitor instance with mocked dependencies"""
    with patch("src.monitoring.health.psutil") as mock_psutil:
        # Setup psutil mocks
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.virtual_memory.return_value = Mock(
            total=8000000000, available=4000000000, percent=50.0
        )
        mock_psutil.disk_usage.return_value = Mock(
            total=100000000000, used=50000000000, free=50000000000, percent=50.0
        )
        mock_psutil.sensors_temperatures.return_value = {}
        mock_psutil.boot_time.return_value = time.time() - 3600

        monitor = HealthMonitor(mock_platform_sync, interval=60)
        yield monitor, mock_psutil


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization"""

    def test_init_defaults(self, mock_platform_sync):
        """Test initialization with defaults"""
        with patch("src.monitoring.health.psutil"):
            monitor = HealthMonitor(mock_platform_sync)

            assert monitor.platform_sync == mock_platform_sync
            assert monitor.interval == 300
            assert monitor.running is False
            assert monitor._thread is None
            assert monitor.devices_status == []
            assert monitor.last_metrics == {}

    def test_init_custom_interval(self, mock_platform_sync):
        """Test initialization with custom interval"""
        with patch("src.monitoring.health.psutil"):
            monitor = HealthMonitor(mock_platform_sync, interval=60)

            assert monitor.interval == 60


class TestHealthMonitorStartStop:
    """Tests for start/stop methods"""

    def test_start(self, health_monitor):
        """Test starting monitor"""
        monitor, _ = health_monitor

        monitor.start()

        assert monitor.running is True
        assert monitor._thread is not None
        assert monitor._thread.is_alive()
        assert monitor._thread.daemon is True

        monitor.stop()

    def test_start_already_running(self, health_monitor):
        """Test starting when already running"""
        monitor, _ = health_monitor

        monitor.start()
        first_thread = monitor._thread
        monitor.start()  # Should not create new thread

        assert monitor._thread == first_thread

        monitor.stop()

    def test_stop(self, health_monitor):
        """Test stopping monitor"""
        monitor, _ = health_monitor

        monitor.start()
        assert monitor.running is True

        monitor.stop()

        assert monitor.running is False
        assert monitor._thread is None

    def test_stop_not_running(self, health_monitor):
        """Test stopping when not running"""
        monitor, _ = health_monitor

        monitor.stop()  # Should not raise

        assert monitor.running is False
        assert monitor._thread is None


class TestHealthMonitorCollectMetrics:
    """Tests for _collect_metrics method"""

    def test_collect_metrics_basic(self, health_monitor):
        """Test basic metrics collection"""
        monitor, mock_psutil = health_monitor

        metrics = monitor._collect_metrics()

        assert "timestamp" in metrics
        assert "cpu" in metrics
        assert "memory" in metrics
        assert "disk" in metrics
        assert "temperature" in metrics
        assert "uptime_seconds" in metrics

        assert metrics["cpu"]["percent"] == 50.0
        assert metrics["cpu"]["count"] == 4
        assert metrics["memory"]["percent"] == 50.0
        assert metrics["disk"]["percent"] == 50.0

    def test_collect_metrics_with_temperature(self, health_monitor):
        """Test metrics collection with temperature"""
        monitor, mock_psutil = health_monitor

        mock_psutil.sensors_temperatures.return_value = {"cpu_thermal": [Mock(current=45.0)]}

        metrics = monitor._collect_metrics()

        assert metrics["temperature"] == 45.0

    def test_collect_metrics_raspberry_pi_temperature(self, health_monitor):
        """Test metrics collection with Raspberry Pi temperature"""
        monitor, mock_psutil = health_monitor

        mock_psutil.sensors_temperatures.return_value = {"bcm2835_thermal": [Mock(current=50.0)]}

        metrics = monitor._collect_metrics()

        assert metrics["temperature"] == 50.0

    def test_collect_metrics_handles_error(self, health_monitor):
        """Test metrics collection handles errors gracefully"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.side_effect = Exception("PSUtil error")

        metrics = monitor._collect_metrics()

        assert "error" in metrics
        assert "timestamp" in metrics
        assert "PSUtil error" in metrics["error"]


class TestHealthMonitorUpdateDeviceStatus:
    """Tests for update_device_status method"""

    def test_update_device_status(self, health_monitor):
        """Test updating device status"""
        monitor, _ = health_monitor

        devices = [
            {"ip": "192.168.1.101", "connected": True},
            {"ip": "192.168.1.102", "connected": False},
        ]

        monitor.update_device_status(devices)

        assert monitor.devices_status == devices

    def test_update_device_status_empty(self, health_monitor):
        """Test updating with empty list"""
        monitor, _ = health_monitor

        monitor.update_device_status([])

        assert monitor.devices_status == []


class TestHealthMonitorGetCurrentMetrics:
    """Tests for get_current_metrics method"""

    def test_get_current_metrics(self, health_monitor):
        """Test getting current metrics"""
        monitor, _ = health_monitor

        metrics = monitor.get_current_metrics()

        assert isinstance(metrics, dict)

    def test_get_current_metrics_returns_copy(self, health_monitor):
        """Test that get_current_metrics returns a copy"""
        monitor, _ = health_monitor

        metrics1 = monitor.get_current_metrics()
        metrics2 = monitor.get_current_metrics()

        assert metrics1 is not metrics2
        assert metrics1 == metrics2


class TestHealthMonitorGetSystemHealth:
    """Tests for get_system_health method"""

    def test_get_system_health_healthy(self, health_monitor):
        """Test system health when all metrics are normal"""
        monitor, mock_psutil = health_monitor

        # Set normal metrics
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = Mock(percent=50.0)
        mock_psutil.disk_usage.return_value = Mock(percent=50.0)
        mock_psutil.sensors_temperatures.return_value = {}

        monitor.devices_status = [
            {"ip": "192.168.1.101", "connected": True},
            {"ip": "192.168.1.102", "connected": True},
        ]

        health = monitor.get_system_health()

        assert health["status"] == "healthy"
        assert health["issues"] == []
        assert health["devices_count"] == 2
        assert health["devices_online"] == 2

    def test_get_system_health_cpu_warning(self, health_monitor):
        """Test system health with high CPU"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.return_value = 95.0
        mock_psutil.virtual_memory.return_value = Mock(percent=50.0)
        mock_psutil.disk_usage.return_value = Mock(percent=50.0)
        mock_psutil.sensors_temperatures.return_value = {}

        monitor.last_metrics = monitor._collect_metrics()

        health = monitor.get_system_health()

        assert health["status"] == "warning"
        assert "CPU usage high" in health["issues"]

    def test_get_system_health_memory_warning(self, health_monitor):
        """Test system health with high memory"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = Mock(percent=95.0)
        mock_psutil.disk_usage.return_value = Mock(percent=50.0)
        mock_psutil.sensors_temperatures.return_value = {}

        monitor.last_metrics = monitor._collect_metrics()

        health = monitor.get_system_health()

        assert health["status"] == "warning"
        assert "Memory usage high" in health["issues"]

    def test_get_system_health_disk_critical(self, health_monitor):
        """Test system health with critical disk"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = Mock(percent=50.0)
        mock_psutil.disk_usage.return_value = Mock(percent=95.0)
        mock_psutil.sensors_temperatures.return_value = {}

        monitor.last_metrics = monitor._collect_metrics()

        health = monitor.get_system_health()

        assert health["status"] == "critical"
        assert "Disk usage critical" in health["issues"]

    def test_get_system_health_temperature_critical(self, health_monitor):
        """Test system health with critical temperature"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = Mock(percent=50.0)
        mock_psutil.disk_usage.return_value = Mock(percent=50.0)
        mock_psutil.sensors_temperatures.return_value = {"cpu_thermal": [Mock(current=85.0)]}

        monitor.last_metrics = monitor._collect_metrics()

        health = monitor.get_system_health()

        assert health["status"] == "critical"
        assert "Temperature critical" in health["issues"]

    def test_get_system_health_temperature_warning(self, health_monitor):
        """Test system health with high temperature"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = Mock(percent=50.0)
        mock_psutil.disk_usage.return_value = Mock(percent=50.0)
        mock_psutil.sensors_temperatures.return_value = {"cpu_thermal": [Mock(current=75.0)]}

        monitor.last_metrics = monitor._collect_metrics()

        health = monitor.get_system_health()

        assert health["status"] == "warning"
        assert "Temperature high" in health["issues"]

    def test_get_system_health_mixed_issues(self, health_monitor):
        """Test system health with multiple issues"""
        monitor, mock_psutil = health_monitor

        mock_psutil.cpu_percent.return_value = 95.0
        mock_psutil.virtual_memory.return_value = Mock(percent=95.0)
        mock_psutil.disk_usage.return_value = Mock(percent=95.0)
        mock_psutil.sensors_temperatures.return_value = {}

        monitor.last_metrics = monitor._collect_metrics()

        health = monitor.get_system_health()

        assert health["status"] == "critical"  # Most severe
        assert len(health["issues"]) == 3


class TestHealthMonitorRunLoop:
    """Tests for _run loop"""

    def test_run_loop_calls_send_heartbeat(self, health_monitor):
        """Test run loop calls send_heartbeat"""
        monitor, mock_psutil = health_monitor

        # Start and stop quickly
        monitor.start()
        time.sleep(0.1)  # Let it run one iteration
        monitor.stop()

        # Should have called send_heartbeat
        assert monitor.platform_sync.send_heartbeat.called

    def test_run_loop_handles_exception(self, health_monitor):
        """Test run loop handles exceptions gracefully"""
        monitor, mock_psutil = health_monitor

        # Make send_heartbeat raise
        monitor.platform_sync.send_heartbeat.side_effect = Exception("Network error")

        monitor.start()
        time.sleep(0.1)
        monitor.stop()

        # Should not have crashed
        assert monitor.running is False


class TestHealthMonitorIntegration:
    """Integration tests for HealthMonitor with Collector"""

    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    def test_collector_integrates_health_monitor(
        self, mock_platform, mock_buffer, mock_health_class
    ):
        """Test collector integrates health monitor"""
        from src.core.collector import AttendanceCollector
        from src.core.config import Config

        mock_config = Mock(spec=Config)
        mock_config.get.side_effect = lambda key, default=None: {
            "platform.url": "https://test.example.com",
            "platform.api_key": "key",
            "platform.tenant_id": "tenant",
            "poll_interval_seconds": 60,
            "sync_interval_seconds": 10,
            "buffer.max_records": 1000,
            "health.heartbeat_interval": 60,
            "devices": [],
        }.get(key, default)

        mock_health_instance = Mock()
        mock_health_class.return_value = mock_health_instance

        collector = AttendanceCollector(mock_config)

        assert collector.health_monitor == mock_health_instance
        mock_health_class.assert_called_once()
        # Verify it was called with platform_sync and interval
        call_args = mock_health_class.call_args
        assert call_args[1]["interval"] == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
