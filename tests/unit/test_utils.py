"""
Unit tests for utils modules
"""

import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.utils.helpers import (
    format_bytes,
    get_disk_usage,
    get_memory_usage,
    get_system_info,
    is_running_as_root,
    truncate_string,
)
from src.utils.logging import setup_logging


class TestLogging:
    """Tests for logging setup"""

    def test_setup_logging_text(self):
        """Test text format logging setup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_logging(
                level=logging.DEBUG,
                log_format='text',
                log_dir=Path(tmpdir),
                max_size_mb=10,
                backup_count=5
            )
            assert logger is not None
            assert isinstance(logger, logging.Logger)

    def test_setup_logging_json(self):
        """Test JSON format logging setup"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_logging(
                level=logging.INFO,
                log_format='json',
                log_dir=Path(tmpdir),
                max_size_mb=10,
                backup_count=5
            )
            assert logger is not None

    def test_setup_logging_creates_file(self):
        """Test that logging creates log file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(
                level=logging.DEBUG,
                log_format='text',
                log_dir=Path(tmpdir),
                max_size_mb=10,
                backup_count=5
            )
            log_files = list(Path(tmpdir).glob("*.log"))
            assert len(log_files) > 0


class TestHelpers:
    """Tests for helpers module"""

    @patch('src.utils.helpers.platform.system')
    @patch('src.utils.helpers.platform.release')
    @patch('src.utils.helpers.platform.machine')
    @patch('src.utils.helpers.platform.processor')
    @patch('src.utils.helpers.platform.node')
    @patch('src.utils.helpers.platform.python_version')
    @patch('src.utils.helpers.platform.python_implementation')
    @patch('src.utils.helpers.psutil.cpu_count')
    @patch('src.utils.helpers.psutil.virtual_memory')
    def test_get_system_info(
        self,
        mock_memory,
        mock_cpu,
        mock_py_impl,
        mock_py_ver,
        mock_node,
        mock_proc,
        mock_machine,
        mock_release,
        mock_system,
    ):
        """Test get_system_info"""
        mock_system.return_value = 'Linux'
        mock_release.return_value = '5.15.0'
        mock_machine.return_value = 'armv7l'
        mock_proc.return_value = 'ARMv7'
        mock_node.return_value = 'test-host'
        mock_py_ver.return_value = '3.12.0'
        mock_py_impl.return_value = 'CPython'
        mock_cpu.return_value = 4
        # 4 GB = 4 * 1024^3 = 4294967296 bytes
        mock_memory.return_value = Mock(total=4294967296, available=2000000000, percent=50)

        info = get_system_info()

        assert 'Linux' in info['os']
        assert '5.15.0' in info['os']
        assert 'armv7l' in info['os']
        assert '3.12.0' in info['python']
        assert 'CPython' in info['python']
        assert '4' in info['cpu']
        assert 'ARMv7' in info['cpu']
        assert '4.00 GB' in info['ram']
        assert info['hostname'] == 'test-host'

    def test_format_bytes(self):
        """Test format_bytes"""
        assert format_bytes(0) == "0.00 B"
        assert format_bytes(512) == "512.00 B"
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"

    @patch('src.utils.helpers.psutil.disk_usage')
    def test_get_disk_usage(self, mock_disk):
        """Test get_disk_usage"""
        mock_disk.return_value = Mock(
            total=16000000000, used=8000000000, free=8000000000, percent=50.0
        )

        usage = get_disk_usage('/')
        assert usage['total_gb'] == 16000000000 / (1024 ** 3)
        assert usage['used_gb'] == 8000000000 / (1024 ** 3)
        assert usage['free_gb'] == 8000000000 / (1024 ** 3)
        assert usage['percent'] == 50.0

    @patch('src.utils.helpers.psutil.virtual_memory')
    @patch('src.utils.helpers.psutil.Process')
    @patch('src.utils.helpers.os.getpid')
    def test_get_memory_usage(self, mock_getpid, mock_process, mock_memory):
        """Test get_memory_usage"""
        mock_memory.return_value = Mock(percent=60.0)
        mock_getpid.return_value = 12345
        mock_process.return_value.memory_info.return_value = Mock(rss=50 * 1024 * 1024)

        usage = get_memory_usage()
        assert usage['system_percent'] == 60.0
        assert usage['process_mb'] == 50.0

    @patch('src.utils.helpers.os.geteuid')
    def test_is_running_as_root_true(self, mock_geteuid):
        """Test is_running_as_root when root"""
        mock_geteuid.return_value = 0
        assert is_running_as_root() is True

    @patch('src.utils.helpers.os.geteuid')
    def test_is_running_as_root_false(self, mock_geteuid):
        """Test is_running_as_root when not root"""
        mock_geteuid.return_value = 1000
        assert is_running_as_root() is False

    def test_truncate_string(self):
        """Test truncate_string"""
        assert truncate_string("short") == "short"
        assert truncate_string("a" * 50) == "a" * 50
        assert truncate_string("a" * 51, 50) == "a" * 47 + "..."
        assert truncate_string("hello world", 8) == "hello..."
