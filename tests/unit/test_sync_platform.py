"""
Unit tests for PlatformSync
"""

from unittest.mock import Mock, patch

import pytest
import requests

from src.sync.platform import PlatformSync


class TestPlatformSync:
    """Tests for PlatformSync"""

    @pytest.fixture
    def platform_sync(self):
        return PlatformSync(
            platform_url='https://test.example.com',
            api_key='test-key',
            tenant_id='test-tenant',
            timeout=30,
            retry_attempts=3,
        )

    def test_init(self, platform_sync):
        """Test initialization"""
        assert platform_sync.platform_url == 'https://test.example.com'
        assert platform_sync.api_key == 'test-key'
        assert platform_sync.tenant_id == 'test-tenant'
        assert platform_sync.timeout == 30
        assert 'Authorization' in platform_sync.session.headers
        assert platform_sync.session.headers['Authorization'] == 'Bearer test-key'
        assert platform_sync.session.headers['X-Tenant-ID'] == 'test-tenant'

    @patch('src.sync.platform.requests.Session.post')
    def test_sync_attendance_success(self, mock_post, platform_sync):
        """Test successful attendance sync"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        records = [
            {
                'user_id': '1',
                'timestamp': '2026-03-03T08:00:00',
                'status': 0,
                'device_ip': '192.168.1.101',
                'punch_type': 'entrada',
            }
        ]

        result = platform_sync.sync_attendance(records)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://test.example.com/api/v1/attendance/sync'
        assert 'records' in call_args[1]['json']

    @patch('src.sync.platform.requests.Session.post')
    def test_sync_attendance_empty_records(self, mock_post, platform_sync):
        """Test sync with empty records"""
        result = platform_sync.sync_attendance([])
        assert result is True
        mock_post.assert_not_called()

    @patch('src.sync.platform.requests.Session.post')
    def test_sync_attendance_timeout(self, mock_post, platform_sync):
        """Test sync with timeout"""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        records = [
            {
                'user_id': '1',
                'timestamp': '2026-03-03T08:00:00',
                'status': 0,
                'device_ip': '192.168.1.101',
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False

    @patch('src.sync.platform.requests.Session.post')
    def test_sync_attendance_connection_error(self, mock_post, platform_sync):
        """Test sync with connection error"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection error")

        records = [
            {
                'user_id': '1',
                'timestamp': '2026-03-03T08:00:00',
                'status': 0,
                'device_ip': '192.168.1.101',
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False

    @patch('src.sync.platform.requests.Session.post')
    def test_sync_attendance_http_error(self, mock_post, platform_sync):
        """Test sync with HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Unauthorized")
        mock_post.return_value = mock_response

        records = [
            {
                'user_id': '1',
                'timestamp': '2026-03-03T08:00:00',
                'status': 0,
                'device_ip': '192.168.1.101',
            }
        ]
        result = platform_sync.sync_attendance(records)

        assert result is False

    @patch('src.sync.platform.requests.Session.post')
    def test_send_heartbeat_success(self, mock_post, platform_sync):
        """Test successful heartbeat"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        metrics = {'cpu': {'percent': 50}}
        devices_status = [{'ip': '192.168.1.101', 'connected': True}]

        result = platform_sync.send_heartbeat(metrics, devices_status)

        assert result is True
        mock_post.assert_called_once()

    @patch('src.sync.platform.requests.Session.post')
    def test_send_heartbeat_failure(self, mock_post, platform_sync):
        """Test heartbeat failure"""
        mock_post.side_effect = Exception("Error")

        result = platform_sync.send_heartbeat({}, [])

        assert result is False

    @patch('src.sync.platform.requests.Session.get')
    def test_get_config_success(self, mock_get, platform_sync):
        """Test get config success"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'poll_interval': 300}
        mock_get.return_value = mock_response

        config = platform_sync.get_config()

        assert config == {'poll_interval': 300}
        mock_get.assert_called_once_with(
            'https://test.example.com/api/v1/collector/config', timeout=10
        )

    @patch('src.sync.platform.requests.Session.get')
    def test_get_config_failure(self, mock_get, platform_sync):
        """Test get config failure"""
        mock_get.side_effect = Exception("Error")

        config = platform_sync.get_config()

        assert config is None

    @patch('src.sync.platform.requests.Session.get')
    def test_check_version_success(self, mock_get, platform_sync):
        """Test check version success"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'latest_version': '1.1.0'}
        mock_get.return_value = mock_response

        version = platform_sync.check_version()

        assert version == '1.1.0'

    @patch('src.sync.platform.requests.Session.get')
    def test_download_update_success(self, mock_get, platform_sync):
        """Test download update success"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b'binary content'
        mock_get.return_value = mock_response

        content = platform_sync.download_update('1.1.0')

        assert content == b'binary content'

    @patch('src.sync.platform.requests.Session.post')
    def test_report_error_success(self, mock_post, platform_sync):
        """Test report error success"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = platform_sync.report_error(
            'test_error', 'Something went wrong', {'context': 'data'}
        )

        assert result is True

    @patch('src.sync.platform.requests.Session.post')
    def test_report_error_failure(self, mock_post, platform_sync):
        """Test report error failure"""
        mock_post.side_effect = Exception("Error")

        result = platform_sync.report_error('test_error', 'Something went wrong', {})

        assert result is False
