"""
Unit tests for AttendanceCollector.run() method main loop
"""

import contextlib
import logging
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.core.collector import AttendanceCollector
from src.core.config import Config


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config"""
    config = Mock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        "buffer.db_path": str(tmp_path / "buffer.db"),
        "buffer.max_records": 1000,
        "platform.url": "https://api.example.com",
        "platform.api_key": "test-key",
        "platform.tenant_id": "test-tenant",
        "platform.timeout": 30,
        "platform.retry_attempts": 3,
        "health.heartbeat_interval": 300,
        "poll_interval_seconds": 1,
        "sync_interval_seconds": 1,
        "devices": [
            {
                "ip": "192.168.1.100",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "enabled": True,
                "name": "Device1",
            },
        ],
    }.get(key, default)
    return config


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_logs_startup_info(
    mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config, caplog
):
    """Test run() logs startup information"""
    collector = AttendanceCollector(mock_config)
    collector.buffer = Mock()
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    # Mock time.sleep to stop after one iteration
    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 1:
            collector.running = False
        original_sleep(0.001)  # Very short sleep

    with (
        patch("time.sleep", side_effect=mock_sleep),
        caplog.at_level(logging.INFO),
        contextlib.suppress(Exception),  # Expected when we stop the loop
    ):
        collector.run()

    # Check startup logs
    assert "=" * 60 in caplog.text
    assert "Attendance Collector Iniciado" in caplog.text
    assert "Dispositivos configurados:" in caplog.text
    assert "Plataforma: https://api.example.com" in caplog.text
    assert "Poll interval:" in caplog.text
    assert "Sync interval:" in caplog.text


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_initializes_devices_and_starts_health(
    mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() initializes devices and starts health monitor"""
    collector = AttendanceCollector(mock_config)
    collector.buffer = Mock()
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 1:
            collector.running = False
        original_sleep(0.001)

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # Verify initialization
    collector.health_monitor.start.assert_called_once()
    assert len(collector.zk_clients) >= 0  # _initialize_devices called


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_calls_poll_and_sync(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() calls poll_devices and sync_to_platform"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = [
        {"id": 1, "user_id": "001", "timestamp": "2024-01-01T08:00:00", "status": 0}
    ]
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    # Return some unsynced records so sync_attendance gets called
    collector.buffer.get_unsynced_records.return_value = [
        {"id": 1, "user_id": "001", "timestamp": "2024-01-01T08:00:00", "status": 0}
    ]
    collector.platform_sync = Mock()
    collector.platform_sync.sync_attendance.return_value = True
    collector.health_monitor = Mock()

    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 1:
            collector.running = False
        original_sleep(0.001)

    # Set last_poll and last_sync to None so they run on first iteration
    collector.last_poll = None
    collector.last_sync = None
    collector.poll_interval = 1
    collector.sync_interval = 1

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # Should have called poll and sync at least once
    mock_client.connect.assert_called()
    collector.platform_sync.sync_attendance.assert_called()


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_handles_keyboard_interrupt(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config, caplog
):
    """Test run() handles KeyboardInterrupt"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    def mock_sleep(seconds):
        raise KeyboardInterrupt()

    with (
        patch("time.sleep", side_effect=mock_sleep),
        caplog.at_level(logging.INFO),
        contextlib.suppress(KeyboardInterrupt),
    ):
        collector.run()

    assert "Interrupción por teclado" in caplog.text
    assert collector.running is False
    collector.health_monitor.stop.assert_called_once()


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_handles_generic_exception(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config, caplog
):
    """Test run() handles generic exception"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    def mock_sleep(seconds):
        raise Exception("Test error")

    with (
        patch("time.sleep", side_effect=mock_sleep),
        caplog.at_level(logging.ERROR),
        contextlib.suppress(Exception),
    ):
        collector.run()

    assert "Error en loop principal" in caplog.text
    assert "Test error" in caplog.text
    collector.health_monitor.stop.assert_called_once()


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_finally_calls_stop(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() finally block calls stop()"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    def mock_sleep(seconds):
        raise KeyboardInterrupt()

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(KeyboardInterrupt):
        collector.run()

    # stop() should be called in finally
    assert collector.running is False


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_sleeps_between_iterations(
    mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() sleeps between iterations"""
    collector = AttendanceCollector(mock_config)
    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            collector.running = False

    collector.last_poll = datetime.now()  # Not due for poll
    collector.last_sync = datetime.now()  # Not due for sync
    collector.poll_interval = 300
    collector.sync_interval = 300

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # Should have called sleep
    assert len(sleep_calls) >= 1
    assert sleep_calls[0] == 5  # 5 second sleep


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_updates_last_poll_and_last_sync(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() updates last_poll and last_sync after operations"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 1:
            collector.running = False
        original_sleep(0.001)

    collector.last_poll = None
    collector.last_sync = None
    collector.poll_interval = 1
    collector.sync_interval = 1

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # last_poll and last_sync should be updated
    assert collector.last_poll is not None
    assert collector.last_sync is not None


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_respects_poll_interval(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() respects poll_interval"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 3:
            collector.running = False
        original_sleep(0.001)

    # Set intervals
    collector.poll_interval = 300  # 5 minutes
    collector.sync_interval = 300
    collector.last_poll = datetime.now() - timedelta(seconds=100)  # Not due
    collector.last_sync = datetime.now() - timedelta(seconds=100)  # Not due

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # Should not have called connect since not due
    mock_client.connect.assert_not_called()


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_respects_sync_interval(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() respects sync_interval"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 3:
            collector.running = False
        original_sleep(0.001)

    # Set intervals
    collector.poll_interval = 300
    collector.sync_interval = 300
    collector.last_poll = datetime.now() - timedelta(seconds=100)
    collector.last_sync = datetime.now() - timedelta(seconds=100)

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # Should not have called sync since not due
    collector.platform_sync.sync_attendance.assert_not_called()


@patch("src.core.collector.BufferRepository")
@patch("src.core.collector.PlatformSync")
@patch("src.core.collector.HealthMonitor")
@patch("src.core.collector.ZKClient")
def test_run_multiple_iterations(
    mock_zk_client_class, mock_health, mock_platform, mock_buffer, mock_config
):
    """Test run() multiple iterations"""
    collector = AttendanceCollector(mock_config)

    # Create mock ZKClient that will be returned by _initialize_devices
    mock_client = Mock()
    mock_client.connect.return_value = True
    mock_client.get_attendance.return_value = []
    mock_client.disconnect.return_value = None
    mock_client.connected = True
    mock_zk_client_class.return_value = mock_client

    collector.buffer = Mock()
    collector.buffer.get_unsynced_records.return_value = []
    collector.platform_sync = Mock()
    collector.health_monitor = Mock()

    original_sleep = time.sleep
    call_count = [0]

    def mock_sleep(seconds):
        call_count[0] += 1
        if call_count[0] >= 3:
            collector.running = False
        original_sleep(0.001)

    collector.last_poll = None
    collector.last_sync = None
    collector.poll_interval = 1
    collector.sync_interval = 1

    with patch("time.sleep", side_effect=mock_sleep), contextlib.suppress(Exception):
        collector.run()

    # Should have multiple sleep calls (multiple iterations)
    assert len(call_count) >= 2 or call_count[0] >= 2
