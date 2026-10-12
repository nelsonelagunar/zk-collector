"""
Unit tests for PlatformSync module
"""

from unittest.mock import Mock, patch

import pytest
import requests

from src.sync.platform import PlatformSync


@pytest.fixture
def platform_sync():
    """PlatformSync instance with mocked session"""
    with patch("src.sync.platform.requests.Session") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        sync = PlatformSync(
            platform_url="https://test.example.com",
            api_key="test-key",
            tenant_id="test-tenant",
            timeout=30,
            retry_attempts=3,
        )
        sync.session = mock_session
        yield sync, mock_session


class TestPlatformSyncInit:
    """Tests for PlatformSync initialization"""

    def test_init(self):
        """Test initialization"""
        with patch("src.sync.platform.requests.Session"):
            sync = PlatformSync(
                platform_url="https://test.example.com/",
                api_key="test-key",
                tenant_id="test-tenant",
                timeout=30,
                retry_attempts=3,
            )

            assert sync.platform_url == "https://test.example.com"  # trailing slash removed
            assert sync.api_key == "test-key"
            assert sync.tenant_id == "test-tenant"
            assert sync.timeout == 30

    def test_init_strips_trailing_slash(self):
        """Test platform_url trailing slash is stripped"""
        with patch("src.sync.platform.requests.Session"):
            sync = PlatformSync(
                platform_url="https://test.example.com/", api_key="key", tenant_id="tenant"
            )
            assert sync.platform_url == "https://test.example.com"

    def test_init_session_headers(self):
        """Test session headers are set correctly"""
        with patch("src.sync.platform.requests.Session") as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            PlatformSync(
                platform_url="https://test.example.com", api_key="test-key", tenant_id="test-tenant"
            )

            # Check headers were set
            mock_session.headers.update.assert_called_once()
            headers = mock_session.headers.update.call_args[0][0]
            assert headers["Authorization"] == "Bearer test-key"
            assert headers["X-Tenant-ID"] == "test-tenant"
            assert headers["Content-Type"] == "application/json"
            assert headers["Accept-Encoding"] == "gzip, deflate"


class TestSyncAttendance:
    """Tests for sync_attendance method"""

    def test_sync_attendance_success(self, platform_sync):
        """Test successful sync"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
                "punch_type": "entrada",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is True
        mock_session.post.assert_called_once()

        # Verify endpoint
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://test.example.com/api/v1/attendance/sync"

        # Verify payload
        payload = call_args[1]["json"]
        assert len(payload["records"]) == 1
        assert payload["records"][0]["user_id"] == "1"
        assert payload["records"][0]["timestamp"] == "2026-03-03T08:00:00"
        assert payload["records"][0]["status"] == 0
        assert payload["records"][0]["device_ip"] == "192.168.1.101"
        assert payload["records"][0]["punch_type"] == "entrada"
        assert "synced_at" in payload
        assert "collector_version" in payload

    def test_sync_attendance_multiple_records(self, platform_sync):
        """Test sync with multiple records"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
                "punch_type": "entrada",
            },
            {
                "user_id": "2",
                "timestamp": "2026-03-03T17:00:00",
                "status": 1,
                "device_ip": "192.168.1.101",
                "punch_type": "salida",
            },
            {
                "user_id": "3",
                "timestamp": "2026-03-04T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.102",
                "punch_type": "entrada",
            },
        ]

        result = sync.sync_attendance(records)

        assert result is True
        payload = mock_session.post.call_args[1]["json"]
        assert len(payload["records"]) == 3

    def test_sync_attendance_empty_list(self, platform_sync):
        """Test sync with empty records list"""
        sync, mock_session = platform_sync

        result = sync.sync_attendance([])

        assert result is True
        mock_session.post.assert_not_called()

    def test_sync_attendance_timeout(self, platform_sync):
        """Test sync handles timeout"""
        sync, mock_session = platform_sync

        mock_session.post.side_effect = requests.exceptions.Timeout("Request timeout")

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_connection_error(self, platform_sync):
        """Test sync handles connection error"""
        sync, mock_session = platform_sync

        mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_http_error_401(self, platform_sync):
        """Test sync handles 401 error"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )
        mock_session.post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_http_error_404(self, platform_sync):
        """Test sync handles 404 error"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_session.post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_http_error_500(self, platform_sync):
        """Test sync handles 500 error"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )
        mock_session.post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_unexpected_error(self, platform_sync):
        """Test sync handles unexpected error"""
        sync, mock_session = platform_sync

        mock_session.post.side_effect = Exception("Unexpected error")

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
            }
        ]

        result = sync.sync_attendance(records)

        assert result is False


class TestSendHeartbeat:
    """Tests for send_heartbeat method"""

    def test_send_heartbeat_success(self, platform_sync):
        """Test successful heartbeat"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        metrics = {"cpu": 50.5, "memory": 60.2, "disk": 30.1}
        devices_status = [
            {"ip": "192.168.1.101", "status": "online", "last_seen": "2026-03-03T10:00:00"}
        ]

        result = sync.send_heartbeat(metrics, devices_status)

        assert result is True
        mock_session.post.assert_called_once()

        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://test.example.com/api/v1/collector/heartbeat"

        payload = call_args[1]["json"]
        assert payload["metrics"] == metrics
        assert payload["devices"] == devices_status
        assert "timestamp" in payload
        assert "version" in payload

    def test_send_heartbeat_error(self, platform_sync):
        """Test heartbeat handles error"""
        sync, mock_session = platform_sync

        mock_session.post.side_effect = requests.exceptions.ConnectionError("Error")

        result = sync.send_heartbeat({}, [])

        assert result is False


class TestGetConfig:
    """Tests for get_config method"""

    def test_get_config_success(self, platform_sync):
        """Test successful get_config"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"poll_interval": 120, "sync_interval": 30}
        mock_session.get.return_value = mock_response

        config = sync.get_config()

        assert config == {"poll_interval": 120, "sync_interval": 30}
        mock_session.get.assert_called_once_with(
            "https://test.example.com/api/v1/collector/config", timeout=10
        )

    def test_get_config_error(self, platform_sync):
        """Test get_config handles error"""
        sync, mock_session = platform_sync

        mock_session.get.side_effect = requests.exceptions.ConnectionError("Error")

        result = sync.get_config()

        assert result is None


class TestCheckVersion:
    """Tests for check_version method"""

    def test_check_version_success(self, platform_sync):
        """Test successful version check"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"latest_version": "2.0.0"}
        mock_session.get.return_value = mock_response

        version = sync.check_version()

        assert version == "2.0.0"
        mock_session.get.assert_called_once_with(
            "https://test.example.com/api/v1/collector/version", timeout=10
        )

    def test_check_version_no_version_in_response(self, platform_sync):
        """Test version check when response lacks version"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response

        version = sync.check_version()

        assert version is None

    def test_check_version_error(self, platform_sync):
        """Test version check handles error"""
        sync, mock_session = platform_sync

        mock_session.get.side_effect = requests.exceptions.ConnectionError("Error")

        version = sync.check_version()

        assert version is None


class TestDownloadUpdate:
    """Tests for download_update method"""

    def test_download_update_success(self, platform_sync):
        """Test successful update download"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"binary update content"
        mock_session.get.return_value = mock_response

        content = sync.download_update("2.0.0")

        assert content == b"binary update content"
        mock_session.get.assert_called_once_with(
            "https://test.example.com/api/v1/collector/download/2.0.0", timeout=300
        )

    def test_download_update_error(self, platform_sync):
        """Test download_update handles error"""
        sync, mock_session = platform_sync

        mock_session.get.side_effect = requests.exceptions.ConnectionError("Error")

        content = sync.download_update("2.0.0")

        assert content is None


class TestReportError:
    """Tests for report_error method"""

    def test_report_error_success(self, platform_sync):
        """Test successful error reporting"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        result = sync.report_error(
            "sync_error", "Platform unreachable", {"device": "192.168.1.101", "attempt": 3}
        )

        assert result is True
        mock_session.post.assert_called_once()

        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://test.example.com/api/v1/collector/error"

        payload = call_args[1]["json"]
        assert payload["type"] == "sync_error"
        assert payload["message"] == "Platform unreachable"
        assert payload["context"]["device"] == "192.168.1.101"
        assert payload["context"]["attempt"] == 3
        assert "timestamp" in payload
        assert "version" in payload

    def test_report_error_failure(self, platform_sync):
        """Test error reporting failure"""
        sync, mock_session = platform_sync

        mock_session.post.side_effect = requests.exceptions.ConnectionError("Error")

        result = sync.report_error("test", "message", {})

        assert result is False


class TestRetryStrategy:
    """Tests for retry configuration"""

    def test_retry_strategy_configured(self):
        """Test retry strategy is configured on session"""
        with patch("src.sync.platform.requests.Session") as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            PlatformSync(
                platform_url="https://test.example.com",
                api_key="key",
                tenant_id="tenant",
                retry_attempts=5,
            )

            # Verify HTTPAdapter was mounted with retry strategy
            assert mock_session.mount.call_count == 2  # http:// and https://
