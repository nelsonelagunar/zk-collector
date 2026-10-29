"""Tests de sincronizacion horaria de relojes ZKTeco (MYK-421, MYK-410 TZ-1).

AC del issue: mock device con drift 5min se corrige (set_time) y genera
alerta, con log de correccion. Umbral default 60s, configurable via
`clock_sync.threshold_seconds`.
"""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from src.core.clock_sync import (
    CLOCK_DRIFT_THRESHOLD_SECONDS,
    compute_drift_seconds,
    sync_device_clock,
)
from src.core.collector import AttendanceCollector
from src.core.config import Config

SERVER_TIME = datetime(2026, 10, 27, 12, 0, 0)


class FakeZKDevice:
    """Mock de ZKClient con reloj interno desplazable (get_time/set_time)."""

    def __init__(self, ip="10.0.0.99", drift_seconds=0.0, base_time=None):
        self.ip = ip
        self.set_time_calls: list = []
        self._clock = (base_time or datetime.now()) + timedelta(seconds=drift_seconds)

    # API ZKClient usada por el collector
    def connect(self, max_retries=3, retry_delay=2.0):
        return True

    def disconnect(self):
        pass

    def get_attendance(self, clear_after_read=False, disable_device=True, timezone=None):
        return []

    def get_time(self):
        return self._clock

    def set_time(self, new_time):
        self.set_time_calls.append(new_time)
        self._clock = new_time
        return True


class TestComputeDriftSeconds:
    def test_drift_5min(self):
        assert compute_drift_seconds(SERVER_TIME - timedelta(minutes=5), SERVER_TIME) == 300.0

    def test_absolute_value_device_ahead(self):
        assert compute_drift_seconds(SERVER_TIME + timedelta(seconds=90), SERVER_TIME) == 90.0

    def test_not_datetime_returns_none(self):
        assert compute_drift_seconds("2026-10-27 12:00:00", SERVER_TIME) is None
        assert compute_drift_seconds(None, SERVER_TIME) is None

    def test_mixed_awareness_returns_none(self):
        aware = SERVER_TIME.replace(tzinfo=UTC)
        assert compute_drift_seconds(SERVER_TIME, aware) is None


class TestSyncDeviceClock:
    def test_ac_mock_5min_drift_corrected_and_alerts(self, caplog):
        """AC MYK-421: mock con drift 5min se corrige y genera alerta + log."""
        device = FakeZKDevice(drift_seconds=-300, base_time=SERVER_TIME)
        with caplog.at_level(logging.WARNING, logger="src.core.clock_sync"):
            result = sync_device_clock(device, server_time=SERVER_TIME)

        assert result is not None
        assert result.corrected is True
        assert result.drift_seconds == 300.0
        # Se corrigio con la hora del servidor
        assert device.set_time_calls == [SERVER_TIME]
        assert compute_drift_seconds(device.get_time(), SERVER_TIME) == 0.0
        # Alerta + log de correccion
        assert "ALERTA" in caplog.text
        assert "10.0.0.99" in caplog.text
        assert "300" in caplog.text

    def test_below_threshold_no_correction(self):
        device = FakeZKDevice(drift_seconds=10, base_time=SERVER_TIME)
        result = sync_device_clock(device, server_time=SERVER_TIME)
        assert result is not None and result.corrected is False
        assert device.set_time_calls == []

    def test_threshold_boundary_no_correction(self):
        """Drift == umbral NO corrige (la correccion exige drift > umbral)."""
        device = FakeZKDevice(drift_seconds=60, base_time=SERVER_TIME)
        result = sync_device_clock(device, server_time=SERVER_TIME)
        assert result.corrected is False
        assert device.set_time_calls == []

    def test_just_above_threshold_corrects(self):
        device = FakeZKDevice(drift_seconds=60.5, base_time=SERVER_TIME)
        result = sync_device_clock(device, server_time=SERVER_TIME)
        assert result.corrected is True

    def test_default_threshold_60(self):
        assert CLOCK_DRIFT_THRESHOLD_SECONDS == 60

    def test_unreadable_clock_returns_none(self):
        device = Mock(ip="10.0.0.99")
        device.get_time.return_value = None
        assert sync_device_clock(device, server_time=SERVER_TIME) is None
        device.set_time.assert_not_called()

    def test_set_time_failure_alerts_error(self, caplog):
        device = FakeZKDevice(drift_seconds=-300, base_time=SERVER_TIME)
        device.set_time = lambda t: False
        with caplog.at_level(logging.ERROR, logger="src.core.clock_sync"):
            result = sync_device_clock(device, server_time=SERVER_TIME)
        assert result.corrected is False
        assert result.correction_failed is True
        assert "ALERTA" in caplog.text


def _make_collector():
    """Collector con BufferRepository/PlatformSync/HealthMonitor mockeados."""
    config = Mock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        "buffer.db_path": "/tmp/buffer-myk421.db",
        "devices": [],
        "clock_sync.threshold_seconds": 60,
    }.get(key, default)

    with (
        patch("src.core.collector.BufferRepository"),
        patch("src.core.collector.PlatformSync"),
        patch("src.core.collector.HealthMonitor"),
    ):
        return AttendanceCollector(config)


class TestCollectorWiring:
    """MYK-421: el collector usa get_time/set_time en cada poll."""

    def test_threshold_from_config(self):
        collector = _make_collector()
        assert collector.clock_drift_threshold == 60

    def test_poll_corrects_drifted_device_and_alerts(self, caplog):
        """AC: poll con mock drift 5min corrige el reloj y alerta por log."""
        collector = _make_collector()
        device = FakeZKDevice(ip="10.0.0.99", drift_seconds=-300)
        collector.zk_clients = {"10.0.0.99": device}

        with caplog.at_level(logging.WARNING):
            collector.poll_devices()

        assert device.set_time_calls, "set_time nunca llamado: drift no corregido"
        assert compute_drift_seconds(device.get_time(), datetime.now()) <= 60
        assert "ALERTA" in caplog.text
        assert "10.0.0.99" in caplog.text

    def test_poll_synced_device_no_set_time(self):
        collector = _make_collector()
        device = FakeZKDevice(ip="10.0.0.99")
        collector.zk_clients = {"10.0.0.99": device}

        collector.poll_devices()

        assert device.set_time_calls == []

    def test_poll_survives_unreadable_clock(self):
        """Cliente cuyo get_time no devuelve datetime no tumba el poll."""
        collector = _make_collector()
        device = Mock(ip="10.0.0.99")
        device.connect.return_value = True
        device.get_time.return_value = None
        device.get_attendance.return_value = []
        collector.zk_clients = {"10.0.0.99": device}

        collector.poll_devices()  # no debe lanzar

        device.get_attendance.assert_called_once()
