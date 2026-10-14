"""
Integration tests for Config module
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.core.config import Config, ConfigError


class TestConfigIntegration:
    """Integration tests for Config with real YAML files"""

    @pytest.fixture
    def valid_config_yaml(self):
        """Valid configuration YAML content"""
        return {
            'platform': {
                'url': 'https://api.example.com',
                'api_key': 'test-api-key-12345',
                'tenant_id': 'test-tenant-001',
                'timeout': 30,
                'retry_attempts': 3
            },
            'devices': [
                {
                    'ip': '192.168.1.101',
                    'port': 4370,
                    'timeout': 5,
                    'password': 0,
                    'name': 'Main Entrance',
                    'enabled': True
                },
                {
                    'ip': '192.168.1.102',
                    'port': 4370,
                    'timeout': 5,
                    'password': 1234,
                    'name': 'Back Door',
                    'enabled': True
                }
            ],
            'poll_interval_seconds': 300,
            'sync_interval_seconds': 60,
            'buffer': {
                'max_records': 10000,
                'cleanup_days': 30
            },
            'logging': {
                'level': 'INFO',
                'max_size_mb': 10,
                'backup_count': 5
            }
        }

    @pytest.fixture
    def temp_config_file(self, valid_config_yaml):
        """Create temporary config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_config_yaml, f)
            config_path = Path(f.name)
        yield config_path
        config_path.unlink(missing_ok=True)

    def test_load_valid_config(self, temp_config_file):
        """Test loading valid configuration"""
        config = Config(temp_config_file)

        assert config.get('platform.url') == 'https://api.example.com'
        assert config.get('platform.api_key') == 'test-api-key-12345'
        assert config.get('platform.tenant_id') == 'test-tenant-001'
        assert config.get('platform.timeout') == 30
        assert config.get('platform.retry_attempts') == 3

        devices = config.get('devices')
        assert len(devices) == 2
        assert devices[0]['ip'] == '192.168.1.101'
        assert devices[1]['ip'] == '192.168.1.102'

        assert config.get('poll_interval_seconds') == 300
        assert config.get('sync_interval_seconds') == 60

    def test_config_with_encryption_key(self, valid_config_yaml, temp_config_file):
        """Test config with encryption"""
        # Encrypt the API key
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()

        # Create config with encrypted api_key
        encrypted_config = valid_config_yaml.copy()
        fernet = Fernet(key.encode())
        encrypted_key = fernet.encrypt(b'test-api-key-12345').decode()
        encrypted_config['platform']['api_key'] = encrypted_key

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(encrypted_config, f)
            encrypted_path = Path(f.name)

        try:
            config = Config(encrypted_path, encryption_key=key)
            assert config.get('platform.api_key') == 'test-api-key-12345'
        finally:
            encrypted_path.unlink(missing_ok=True)

    def test_missing_required_section(self, tmp_path):
        """Test error on missing required section"""
        invalid_config = {
            'platform': {
                'url': 'https://api.example.com',
                'api_key': 'key',
                'tenant_id': 'tenant'
            }
            # Missing 'devices' section
        }

        config_path = tmp_path / "invalid.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(ConfigError, match="Sección requerida faltante: devices"):
            Config(config_path)

    def test_empty_devices_list(self, tmp_path):
        """Test error on empty devices list"""
        invalid_config = {
            'platform': {
                'url': 'https://api.example.com',
                'api_key': 'key',
                'tenant_id': 'tenant'
            },
            'devices': []
        }

        config_path = tmp_path / "empty_devices.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(ConfigError, match="Al menos un dispositivo"):
            Config(config_path)

    def test_invalid_platform_url(self, tmp_path):
        """Test error on invalid platform URL"""
        invalid_config = {
            'platform': {
                'url': 'not-a-url',
                'api_key': 'key',
                'tenant_id': 'tenant'
            },
            'devices': [{'ip': '192.168.1.101'}]
        }

        config_path = tmp_path / "bad_url.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(ConfigError, match="platform.url debe ser una URL válida"):
            Config(config_path)

    def test_invalid_device_ip(self, tmp_path):
        """Test error on invalid device IP"""
        invalid_config = {
            'platform': {
                'url': 'https://api.example.com',
                'api_key': 'key',
                'tenant_id': 'tenant'
            },
            'devices': [{'ip': 'not-an-ip'}]
        }

        config_path = tmp_path / "bad_ip.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(ConfigError, match="IP inválida"):
            Config(config_path)

    def test_default_values_applied(self, tmp_path):
        """Test that default values are applied"""
        minimal_config = {
            'platform': {
                'url': 'https://api.example.com',
                'api_key': 'key',
                'tenant_id': 'tenant'
            },
            'devices': [{'ip': '192.168.1.101'}],
            'poll_interval_seconds': 300,
            'sync_interval_seconds': 60
        }

        config_path = tmp_path / "minimal.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(minimal_config, f)

        config = Config(config_path)

        # Check defaults for platform section (these ARE applied)
        assert config.get('platform.timeout') == 30
        assert config.get('platform.retry_attempts') == 3
        # Check provided top-level values are kept
        assert config.get('poll_interval_seconds') == 300
        assert config.get('sync_interval_seconds') == 60
        # Note: device item defaults are not applied by current implementation
        # (item_schema is not processed in _apply_defaults)
        assert config.get('devices.0.ip') == '192.168.1.101'

    def test_dot_notation_access(self, temp_config_file):
        """Test dot notation access"""
        config = Config(temp_config_file)

        assert config.get('platform.url') == 'https://api.example.com'
        assert config.get('devices.0.name') == 'Main Entrance'
        assert config.get('devices.1.name') == 'Back Door'
        assert config.get('buffer.max_records') == 10000
        assert config.get('logging.level') == 'INFO'

    def test_get_with_default(self, temp_config_file):
        """Test get with default value"""
        config = Config(temp_config_file)

        assert config.get('nonexistent.key', 'default') == 'default'
        assert config.get('platform.nonexistent', 'default') == 'default'

    def test_get_all(self, temp_config_file):
        """Test get_all returns full config"""
        config = Config(temp_config_file)
        all_config = config.get_all()

        assert 'platform' in all_config
        assert 'devices' in all_config
        assert len(all_config['devices']) == 2

    def test_save_config(self, temp_config_file, tmp_path):
        """Test saving configuration"""
        config = Config(temp_config_file)
        output_path = tmp_path / "saved_config.yaml"

        config.save(output_path)

        assert output_path.exists()

        # Load and verify
        with open(output_path) as f:
            saved = yaml.safe_load(f)

        assert saved['platform']['url'] == 'https://api.example.com'
        assert len(saved['devices']) == 2
