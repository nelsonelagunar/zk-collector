"""
Unit tests for PlatformSync module
"""

from unittest.mock import Mock, patch

import pytest
import requests

from src.sync.platform import PlatformSync


class TestPlatformSync:
    """Tests for PlatformSync class"""

    @pytest.fixture
    def platform_sync(self):
        """Create PlatformSync instance for testing"""
        return PlatformSync(
            platform_url="https://api.example.com",
            api_key="test-api-key",
            tenant_id="test-tenant",
            timeout=30,
            retry_attempts=3,
        )

    def test_init(self):
        """Test PlatformSync initialization"""
        sync = PlatformSync(
            platform_url="https://api.example.com/",
            api_key="test-key",
            tenant_id="tenant-123",
            timeout=60,
            retry_attempts=5,
        )
        assert sync.platform_url == "https://api.example.com"  # trailing slash removed
        assert sync.api_key == "test-key"
        assert sync.tenant_id == "tenant-123"
        assert sync.timeout == 60
        assert sync.session is not None

    def test_init_strips_trailing_slash(self):
        """Test platform URL trailing slash is stripped"""
        sync = PlatformSync(
            platform_url="https://api.example.com/", api_key="key", tenant_id="tenant"
        )
        assert sync.platform_url == "https://api.example.com"

    def test_session_headers(self, platform_sync):
        """Test session has correct headers"""
        headers = platform_sync.session.headers
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["X-Tenant-ID"] == "test-tenant"
        assert headers["Content-Type"] == "application/json"
        assert "gzip" in headers["Accept-Encoding"]

    def test_retry_strategy(self, platform_sync):
        """Test retry strategy is configured"""
        adapters = platform_sync.session.adapters
        assert "https://" in adapters
        assert "http://" in adapters

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_success(self, mock_post, platform_sync):
        """Test successful attendance sync"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
                "punch_type": "checkin",
            },
            {
                "user_id": "2",
                "timestamp": "2026-01-01 09:00:00",
                "status": 1,
                "device_ip": "192.168.1.100",
            },
        ]

        result = platform_sync.sync_attendance(records)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.example.com/api/v1/attendance/sync"
        assert "json" in call_args[1]
        payload = call_args[1]["json"]
        assert payload["records"][0]["user_id"] == "1"
        assert payload["records"][1]["punch_type"] == "unknown"  # default
        assert "synced_at" in payload
        assert payload["collector_version"] == "1.0.0"

    def test_sync_attendance_empty_records(self, platform_sync):
        """Test sync with empty records returns True without calling API"""
        result = platform_sync.sync_attendance([])
        assert result is True
        # Should not make any HTTP call (early return at line 76)

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_timeout(self, mock_post, platform_sync, caplog):
        """Test sync handles timeout"""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False
        assert "Timeout sincronizando" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_connection_error(self, mock_post, platform_sync, caplog):
        """Test sync handles connection error"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False
        assert "Error de conexión" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_http_error_401(self, mock_post, platform_sync, caplog):
        """Test sync handles 401 HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401", response=mock_response
        )
        mock_post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False
        assert "API Key inválida o expirada" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_http_error_404(self, mock_post, platform_sync, caplog):
        """Test sync handles 404 HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404", response=mock_response
        )
        mock_post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False
        assert "Endpoint no encontrado" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_http_error_generic(self, mock_post, platform_sync, caplog):
        """Test sync handles generic HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500", response=mock_response
        )
        mock_post.return_value = mock_response

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False
        assert "Error HTTP" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_sync_attendance_unexpected_error(self, mock_post, platform_sync, caplog):
        """Test sync handles unexpected error"""
        mock_post.side_effect = Exception("Unexpected error")

        records = [
            {
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False
        assert "Error inesperado sincronizando" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_send_heartbeat_success(self, mock_post, platform_sync):
        """Test successful heartbeat"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        metrics = {"cpu": "50%", "ram": "60%"}
        devices_status = [{"ip": "192.168.1.100", "connected": True}]

        result = platform_sync.send_heartbeat(metrics, devices_status)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.example.com/api/v1/collector/heartbeat"
        payload = call_args[1]["json"]
        assert payload["metrics"] == metrics
        assert payload["devices"] == devices_status
        assert "timestamp" in payload
        assert payload["version"] == "1.0.0"

    @patch("src.sync.platform.requests.Session.post")
    def test_send_heartbeat_failure(self, mock_post, platform_sync, caplog):
        """Test heartbeat failure handling"""
        mock_post.side_effect = Exception("Network error")

        result = platform_sync.send_heartbeat({}, [])

        assert result is False
        assert "Error enviando heartbeat" in caplog.text

    @patch("src.sync.platform.requests.Session.get")
    def test_get_config_success(self, mock_get, platform_sync):
        """Test successful config retrieval"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"poll_interval": 300}
        mock_get.return_value = mock_response

        config = platform_sync.get_config()

        assert config == {"poll_interval": 300}
        mock_get.assert_called_once_with(
            "https://api.example.com/api/v1/collector/config", timeout=10
        )

    @patch("src.sync.platform.requests.Session.get")
    def test_get_config_failure(self, mock_get, platform_sync, caplog):
        """Test config retrieval failure"""
        mock_get.side_effect = Exception("Network error")

        config = platform_sync.get_config()

        assert config is None
        assert "Error obteniendo configuración" in caplog.text

    @patch("src.sync.platform.requests.Session.get")
    def test_check_version_success(self, mock_get, platform_sync):
        """Test successful version check"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"latest_version": "2.0.0"}
        mock_get.return_value = mock_response

        version = platform_sync.check_version()

        assert version == "2.0.0"
        mock_get.assert_called_once_with(
            "https://api.example.com/api/v1/collector/version", timeout=10
        )

    @patch("src.sync.platform.requests.Session.get")
    def test_check_version_failure(self, mock_get, platform_sync, caplog):
        """Test version check failure"""
        mock_get.side_effect = Exception("Network error")

        version = platform_sync.check_version()

        assert version is None
        assert "Error verificando versión" in caplog.text

    @patch("src.sync.platform.requests.Session.get")
    def test_download_update_success(self, mock_get, platform_sync):
        """Test successful update download"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"binary-update-data"
        mock_get.return_value = mock_response

        content = platform_sync.download_update("2.0.0")

        assert content == b"binary-update-data"
        mock_get.assert_called_once_with(
            "https://api.example.com/api/v1/collector/download/2.0.0", timeout=300
        )

    @patch("src.sync.platform.requests.Session.get")
    def test_download_update_failure(self, mock_get, platform_sync, caplog):
        """Test update download failure"""
        mock_get.side_effect = Exception("Network error")

        content = platform_sync.download_update("2.0.0")

        assert content is None
        assert "Error descargando actualización" in caplog.text

    @patch("src.sync.platform.requests.Session.post")
    def test_report_error_success(self, mock_post, platform_sync):
        """Test successful error reporting"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = platform_sync.report_error(
            "connection", "Failed to connect", {"device": "192.168.1.100"}
        )

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.example.com/api/v1/collector/error"
        payload = call_args[1]["json"]
        assert payload["type"] == "connection"
        assert payload["message"] == "Failed to connect"
        assert payload["context"] == {"device": "192.168.1.100"}
        assert payload["version"] == "1.0.0"

    @patch("src.sync.platform.requests.Session.post")
    def test_report_error_failure(self, mock_post, platform_sync, caplog):
        """Test error reporting failure"""
        mock_post.side_effect = Exception("Network error")

        result = platform_sync.report_error("test", "test error", {})

        assert result is False
        assert "Error reportando error" in caplog.text
