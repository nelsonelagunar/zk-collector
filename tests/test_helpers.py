"""
Unit tests for helpers module
"""

from unittest.mock import Mock, patch

from src.utils.helpers import (
    format_bytes,
    get_disk_usage,
    get_memory_usage,
    get_system_info,
    is_running_as_root,
    truncate_string,
)


class TestHelpers:
    """Tests for helper functions"""

    @patch("src.utils.helpers.platform")
    @patch("src.utils.helpers.psutil")
    def test_get_system_info(self, mock_psutil, mock_platform):
        """Test get_system_info returns system information"""
        mock_platform.system.return_value = "Linux"
        mock_platform.release.return_value = "6.0.0"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.processor.return_value = "Intel i7"
        mock_platform.node.return_value = "test-host"

        mock_memory = Mock()
        mock_memory.total = 16 * (1024**3)  # 16 GB
        mock_psutil.virtual_memory.return_value = mock_memory
        mock_psutil.cpu_count.return_value = 8

        info = get_system_info()
        assert info["os"] == "Linux 6.0.0 (x86_64)"
        assert info["python"] == "3.12.0 (CPython)"
        assert info["ram"] == "16.00 GB"
        assert info["cpu"] == "8 cores (Intel i7)"
        assert info["hostname"] == "test-host"

    @patch("src.utils.helpers.psutil")
    def test_get_disk_usage(self, mock_psutil):
        """Test get_disk_usage returns disk information"""
        mock_disk = Mock()
        mock_disk.total = 500 * (1024**3)  # 500 GB
        mock_disk.used = 200 * (1024**3)  # 200 GB
        mock_disk.free = 300 * (1024**3)  # 300 GB
        mock_disk.percent = 40.0
        mock_psutil.disk_usage.return_value = mock_disk

        usage = get_disk_usage("/")
        assert usage["total_gb"] == 500.0
        assert usage["used_gb"] == 200.0
        assert usage["free_gb"] == 300.0
        assert usage["percent"] == 40.0

    @patch("src.utils.helpers.os")
    def test_is_running_as_root_true(self, mock_os):
        """Test is_running_as_root returns True for root"""
        mock_os.geteuid.return_value = 0
        assert is_running_as_root() is True

    @patch("src.utils.helpers.os")
    def test_is_running_as_root_false(self, mock_os):
        """Test is_running_as_root returns False for non-root"""
        mock_os.geteuid.return_value = 1000
        assert is_running_as_root() is False

    @patch("src.utils.helpers.psutil")
    @patch("src.utils.helpers.os")
    def test_get_memory_usage(self, mock_os, mock_psutil):
        """Test get_memory_usage returns memory information"""
        mock_os.getpid.return_value = 12345

        mock_memory = Mock()
        mock_memory.percent = 45.5
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 100 * (1024**2)  # 100 MB
        mock_psutil.Process.return_value = mock_process

        usage = get_memory_usage()
        assert usage["system_percent"] == 45.5
        assert usage["process_mb"] == 100.0

    def test_format_bytes_b(self):
        """Test format_bytes for bytes"""
        assert format_bytes(500) == "500.00 B"
        assert format_bytes(0) == "0.00 B"

    def test_format_bytes_kb(self):
        """Test format_bytes for kilobytes"""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"

    def test_format_bytes_mb(self):
        """Test format_bytes for megabytes"""
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1.5 * 1024 * 1024) == "1.50 MB"

    def test_format_bytes_gb(self):
        """Test format_bytes for gigabytes"""
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(2.5 * 1024 * 1024 * 1024) == "2.50 GB"

    def test_format_bytes_tb(self):
        """Test format_bytes for terabytes"""
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"

    def test_format_bytes_pb(self):
        """Test format_bytes for petabytes (edge case)"""
        # Very large number should return PB
        result = format_bytes(1024 * 1024 * 1024 * 1024 * 1024)
        assert "PB" in result

    def test_format_bytes_negative(self):
        """Test format_bytes with negative values"""
        # abs() is NOT used in the function, so negative returns negative
        assert format_bytes(-1024) == "-1.00 KB"

    def test_truncate_string_no_truncate(self):
        """Test truncate_string when under max length"""
        assert truncate_string("short", 50) == "short"
        assert truncate_string("exact50", 7) == "exact50"

    def test_truncate_string_truncate(self):
        """Test truncate_string when over max length"""
        result = truncate_string("this is a very long string", 10)
        assert result == "this is..."
        assert len(result) == 10

    def test_truncate_string_exact_max(self):
        """Test truncate_string at exact max length"""
        assert truncate_string("12345", 5) == "12345"

    def test_truncate_string_small_max(self):
        """Test truncate_string with small max length"""
        # When max_length <= 3, the logic returns ...
        result = truncate_string("hello", 3)
        assert result == "..."

    def test_truncate_string_zero_max(self):
        """Test truncate_string with zero max length"""
        # s[:-3] with max_length=0 gives s[:-3] = "he" for "hello"
        result = truncate_string("hello", 0)
        assert result == "he..."
