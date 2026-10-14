"""
Unit tests for main.py Application class
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.main import Application


class TestApplication:
    """Tests for Application main class"""

    @pytest.fixture
    def temp_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            data_dir = Path(tmpdir) / "data"
            log_dir = Path(tmpdir) / "logs"
            data_dir.mkdir()
            log_dir.mkdir()
            yield config_path, data_dir, log_dir

    def test_init(self, temp_dirs):
        """Test Application initialization"""
        config_path, data_dir, log_dir = temp_dirs

        with patch.dict('os.environ', {
            'CONFIG_PATH': str(config_path),
            'DATA_DIR': str(data_dir),
            'LOG_DIR': str(log_dir)
        }):
            app = Application()

            assert app.config_path == config_path
            assert app.data_dir == data_dir
            assert app.log_dir == log_dir
            assert app.running is False
            assert app.validate_only is False
            assert app.logger is None  # logger is set in initialize()

    @patch('src.main.Config')
    @patch('src.main.AttendanceCollector')
    @patch('src.main.get_system_info')
    @patch('src.main.setup_logging')
    def test_initialize_success(
        self,
        mock_setup_logging,
        mock_get_sysinfo,
        mock_collector_class,
        mock_config_class,
        temp_dirs,
    ):
        """Test successful initialization"""
        config_path, data_dir, log_dir = temp_dirs

        # Create valid config file
        import yaml
        config_data = {
            'platform': {
                'url': 'https://test.com',
                'api_key': 'key',
                'tenant_id': 'tenant',
            },
            'devices': [{'ip': '192.168.1.101'}],
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_get_sysinfo.return_value = {
            'os': 'Linux',
            'python': '3.12',
            'ram': '4 GB',
            'cpu': '4 cores',
        }
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'platform.url': 'https://test.com',
            'platform.api_key': 'key',
            'platform.tenant_id': 'tenant',
            'devices': [{'ip': '192.168.1.101'}],
        }.get(key, default)
        mock_config_class.return_value = mock_config

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ):
            app = Application()
            app.validate_only = False

            result = app.initialize()
            assert result is True
            assert app.logger == mock_logger
            assert app.config == mock_config
            mock_collector_class.assert_called_once_with(mock_config)

    @patch('src.main.Config')
    @patch('src.main.get_system_info')
    @patch('src.main.setup_logging')
    def test_initialize_missing_config(
        self, mock_setup_logging, mock_get_sysinfo, mock_config_class, temp_dirs
    ):
        """Test initialization with missing config file"""
        config_path, data_dir, log_dir = temp_dirs

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_get_sysinfo.return_value = {
            'os': 'Linux',
            'python': '3.12',
            'ram': '4 GB',
            'cpu': '4 cores',
        }

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),  # File doesn't exist
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ):
            app = Application()
            app.validate_only = False

            result = app.initialize()
            assert result is False
            mock_logger.error.assert_called()

    @patch('src.main.Config')
    @patch('src.main.get_system_info')
    @patch('src.main.setup_logging')
    def test_initialize_validate_only(
        self, mock_setup_logging, mock_get_sysinfo, mock_config_class, temp_dirs
    ):
        """Test initialization with validate_only flag"""
        config_path, data_dir, log_dir = temp_dirs

        # Create valid config file
        import yaml
        config_data = {
            'platform': {
                'url': 'https://test.com',
                'api_key': 'key',
                'tenant_id': 'tenant',
            },
            'devices': [{'ip': '192.168.1.101'}],
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_get_sysinfo.return_value = {
            'os': 'Linux',
            'python': '3.12',
            'ram': '4 GB',
            'cpu': '4 cores',
        }
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'platform.url': 'https://test.com',
            'platform.api_key': 'key',
            'platform.tenant_id': 'tenant',
            'devices': [{'ip': '192.168.1.101'}],
        }.get(key, default)
        mock_config_class.return_value = mock_config

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ):
            app = Application()
            app.validate_only = True

            result = app.initialize()
            assert result is True
            mock_logger.info.assert_any_call("✓ Validación de configuración exitosa")

    @patch('src.main.Config')
    @patch('src.main.get_system_info')
    @patch('src.main.setup_logging')
    def test_initialize_invalid_config(
        self, mock_setup_logging, mock_get_sysinfo, mock_config_class, temp_dirs
    ):
        """Test initialization with invalid config (missing required fields)"""
        config_path, data_dir, log_dir = temp_dirs

        # Create invalid config file
        import yaml
        config_data = {'platform': {'url': 'https://test.com'}}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_get_sysinfo.return_value = {
            'os': 'Linux',
            'python': '3.12',
            'ram': '4 GB',
            'cpu': '4 cores',
        }
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'platform.url': 'https://test.com',
            'platform.api_key': None,  # Missing!
            'platform.tenant_id': 'tenant',
            'devices': [{'ip': '192.168.1.101'}],
        }.get(key, default)
        mock_config_class.return_value = mock_config

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ):
            app = Application()
            app.validate_only = False

            result = app.initialize()
            assert result is False
            mock_logger.error.assert_called()

    @patch('src.main.signal.signal')
    def test_setup_signals(self, mock_signal, temp_dirs):
        """Test signal handler setup"""
        config_path, data_dir, log_dir = temp_dirs

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ), patch('src.main.setup_logging'), patch('src.main.get_system_info'):
            app = Application()
            app.logger = Mock()
            app.collector = Mock()

            app._setup_signals()
            assert mock_signal.call_count >= 2  # SIGINT, SIGTERM

    @patch('src.main.Config')
    @patch('src.main.AttendanceCollector')
    @patch('src.main.get_system_info')
    @patch('src.main.setup_logging')
    def test_run_with_keyboard_interrupt(
        self,
        mock_setup_logging,
        mock_get_sysinfo,
        mock_collector_class,
        mock_config_class,
        temp_dirs,
    ):
        """Test run with KeyboardInterrupt"""
        config_path, data_dir, log_dir = temp_dirs

        # Create valid config file
        import yaml
        config_data = {
            'platform': {
                'url': 'https://test.com',
                'api_key': 'key',
                'tenant_id': 'tenant',
            },
            'devices': [{'ip': '192.168.1.101'}],
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_get_sysinfo.return_value = {
            'os': 'Linux',
            'python': '3.12',
            'ram': '4 GB',
            'cpu': '4 cores',
        }
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'platform.url': 'https://test.com',
            'platform.api_key': 'key',
            'platform.tenant_id': 'tenant',
            'devices': [{'ip': '192.168.1.101'}],
        }.get(key, default)
        mock_config_class.return_value = mock_config

        mock_collector = Mock()
        mock_collector.run.side_effect = KeyboardInterrupt()
        mock_collector_class.return_value = mock_collector

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ), patch('src.main.sys.exit') as mock_exit:
            app = Application()
            app.validate_only = False

            app.run()

            mock_collector.run.assert_called_once()
            mock_collector.stop.assert_called_once()
            mock_logger.info.assert_any_call("Interrupción por teclado")
            # KeyboardInterrupt is caught and doesn't call sys.exit(1)
            # Just verify sys.exit wasn't called for KeyboardInterrupt
            mock_exit.assert_not_called()

    @patch('src.main.Config')
    @patch('src.main.AttendanceCollector')
    @patch('src.main.get_system_info')
    @patch('src.main.setup_logging')
    def test_run_with_exception(
        self,
        mock_setup_logging,
        mock_get_sysinfo,
        mock_collector_class,
        mock_config_class,
        temp_dirs,
    ):
        """Test run with exception"""
        config_path, data_dir, log_dir = temp_dirs

        # Create valid config file
        import yaml
        config_data = {
            'platform': {
                'url': 'https://test.com',
                'api_key': 'key',
                'tenant_id': 'tenant',
            },
            'devices': [{'ip': '192.168.1.101'}],
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_get_sysinfo.return_value = {
            'os': 'Linux',
            'python': '3.12',
            'ram': '4 GB',
            'cpu': '4 cores',
        }
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            'platform.url': 'https://test.com',
            'platform.api_key': 'key',
            'platform.tenant_id': 'tenant',
            'devices': [{'ip': '192.168.1.101'}],
        }.get(key, default)
        mock_config_class.return_value = mock_config

        mock_collector = Mock()
        mock_collector.run.side_effect = Exception("Test error")
        mock_collector_class.return_value = mock_collector

        with patch.dict(
            'os.environ',
            {
                'CONFIG_PATH': str(config_path),
                'DATA_DIR': str(data_dir),
                'LOG_DIR': str(log_dir),
            },
        ), patch('src.main.sys.exit') as mock_exit:
            app = Application()
            app.validate_only = False

            app.run()

            mock_collector.run.assert_called_once()
            mock_collector.stop.assert_called_once()
            mock_logger.error.assert_called()
            mock_exit.assert_called_with(1)
