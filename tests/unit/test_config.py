"""
Unit tests for Config module
"""


import pytest
import yaml
from cryptography.fernet import Fernet

from src.core.config import Config, ConfigError


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file for testing"""
    config_data = {
        "platform": {
            "url": "https://test.example.com",
            "api_key": "test-api-key",
            "tenant_id": "test-tenant-id",
            "timeout": 30,
            "retry_attempts": 3,
        },
        "devices": [
            {
                "ip": "192.168.1.101",
            }
        ],
        "poll_interval_seconds": 300,
        "sync_interval_seconds": 60,
    }
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


@pytest.fixture
def encryption_key():
    """Generate a test encryption key"""
    return Fernet.generate_key().decode()


@pytest.fixture
def encrypted_config_file(tmp_path, encryption_key):
    """Create a config file with encrypted sensitive values"""
    fernet = Fernet(encryption_key.encode())

    config_data = {
        "platform": {
            "url": "https://test.example.com",
            "api_key": fernet.encrypt(b"test-api-key").decode(),
            "tenant_id": "test-tenant-id",
        },
        "devices": [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "password": fernet.encrypt(b"secret123").decode(),
                "enabled": True,
            }
        ],
        "poll_interval_seconds": 300,
        "sync_interval_seconds": 60,
    }
    config_file = tmp_path / "encrypted_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file, encryption_key


class TestConfigLoading:
    """Tests for config loading"""

    def test_load_valid_yaml(self, temp_config_file):
        """Test loading valid YAML config"""
        config = Config(temp_config_file)
        assert config.get("platform.url") == "https://test.example.com"
        assert config.get("platform.api_key") == "test-api-key"

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading nonexistent file raises error"""
        with pytest.raises(ConfigError, match="Archivo no encontrado"):
            Config(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML raises error"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")
        with pytest.raises(ConfigError, match="Error parseando YAML"):
            Config(config_file)

    def test_load_with_encryption_key(self, encrypted_config_file):
        """Test loading config with encryption"""
        config_file, encryption_key = encrypted_config_file
        config = Config(config_file, encryption_key=encryption_key)
        assert config.get("platform.api_key") == "test-api-key"
        assert config.get("devices.0.password") == "secret123"


class TestConfigValidation:
    """Tests for config validation"""

    def test_missing_platform_section(self, tmp_path):
        """Test missing platform section raises error"""
        config_data = {
            "devices": [{"ip": "192.168.1.101"}],
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        with pytest.raises(ConfigError, match="Sección requerida faltante: platform"):
            Config(config_file)

    def test_missing_devices_section(self, tmp_path):
        """Test missing devices section raises error"""
        config_data = {
            "platform": {
                "url": "https://test.example.com",
                "api_key": "key",
                "tenant_id": "tenant",
            },
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        with pytest.raises(ConfigError, match="Sección requerida faltante: devices"):
            Config(config_file)

    def test_empty_devices_list(self, tmp_path):
        """Test empty devices list raises error"""
        config_data = {
            "platform": {
                "url": "https://test.example.com",
                "api_key": "key",
                "tenant_id": "tenant",
            },
            "devices": [],
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        with pytest.raises(ConfigError, match="Al menos un dispositivo debe estar configurado"):
            Config(config_file)

    def test_invalid_platform_url(self, tmp_path):
        """Test invalid platform URL raises error"""
        config_data = {
            "platform": {
                "url": "not-a-url",
                "api_key": "key",
                "tenant_id": "tenant",
            },
            "devices": [{"ip": "192.168.1.101"}],
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        with pytest.raises(ConfigError, match="platform.url debe ser una URL válida"):
            Config(config_file)

    def test_invalid_device_ip(self, tmp_path):
        """Test invalid device IP raises error"""
        config_data = {
            "platform": {
                "url": "https://test.example.com",
                "api_key": "key",
                "tenant_id": "tenant",
            },
            "devices": [{"ip": "999.999.999.999"}],
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        with pytest.raises(ConfigError, match="Dispositivo 1: IP inválida"):
            Config(config_file)

    def test_valid_device_ips(self, tmp_path):
        """Test various valid IP formats"""
        valid_ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1", "255.255.255.255", "0.0.0.0"]
        for ip in valid_ips:
            config_data = {
                "platform": {
                    "url": "https://test.example.com",
                    "api_key": "key",
                    "tenant_id": "tenant",
                },
                "devices": [{"ip": ip}],
            }
            config_file = tmp_path / f"config_{ip}.yaml"
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)
            config = Config(config_file)  # Should not raise
            assert config.get("devices.0.ip") == ip


class TestConfigDefaults:
    """Tests for default value application"""

    def test_platform_defaults(self, temp_config_file):
        """Test platform defaults are applied"""
        config = Config(temp_config_file)
        assert config.get("platform.timeout") == 30
        assert config.get("platform.retry_attempts") == 3

    def test_device_defaults(self, temp_config_file):
        """Test device defaults are applied (values not in config get defaults)"""
        config = Config(temp_config_file)
        assert config.get("devices.0.port") == 4370
        assert config.get("devices.0.timeout") == 5
        assert config.get("devices.0.password") == "0"
        # name is not in fixture config, so should get default ''
        assert config.get("devices.0.name") == ""
        assert config.get("devices.0.enabled") is True

    def test_poll_sync_defaults(self, temp_config_file):
        """Test polling and sync interval defaults"""
        config = Config(temp_config_file)
        assert config.get("poll_interval_seconds") == 300
        assert config.get("sync_interval_seconds") == 60

    def test_buffer_defaults(self, temp_config_file):
        """Test buffer defaults"""
        config = Config(temp_config_file)
        assert config.get("buffer.max_records") == 10000
        assert config.get("buffer.cleanup_days") == 30
        assert config.get("buffer.db_path") == ""

    def test_logging_defaults(self, temp_config_file):
        """Test logging defaults"""
        config = Config(temp_config_file)
        assert config.get("logging.level") == "INFO"
        assert config.get("logging.max_size_mb") == 10
        assert config.get("logging.backup_count") == 5
        assert config.get("logging.format") == "text"


class TestConfigEncryption:
    """Tests for encryption/decryption"""

    def test_decrypt_platform_api_key(self, encrypted_config_file):
        """Test platform API key decryption"""
        config_file, encryption_key = encrypted_config_file
        config = Config(config_file, encryption_key=encryption_key)
        assert config.get("platform.api_key") == "test-api-key"

    def test_decrypt_device_password(self, encrypted_config_file):
        """Test device password decryption"""
        config_file, encryption_key = encrypted_config_file
        config = Config(config_file, encryption_key=encryption_key)
        assert config.get("devices.0.password") == "secret123"

    def test_skip_non_encrypted_values(self, temp_config_file, encryption_key):
        """Test non-encrypted values are not decrypted"""
        config = Config(temp_config_file, encryption_key=encryption_key)
        assert config.get("platform.api_key") == "test-api-key"

    def test_looks_encrypted_detection(self, temp_config_file, encryption_key):
        """Test _looks_encrypted helper"""
        config = Config(temp_config_file, encryption_key=encryption_key)
        # Plain text should not look encrypted
        assert config._looks_encrypted("plain-text") is False
        # Fernet token should look encrypted
        fernet = Fernet(encryption_key.encode())
        encrypted = fernet.encrypt(b"test").decode()
        assert config._looks_encrypted(encrypted) is True


class TestConfigGet:
    """Tests for config.get() method"""

    def test_get_simple_key(self, temp_config_file):
        """Test getting simple key"""
        config = Config(temp_config_file)
        assert config.get("platform.url") == "https://test.example.com"

    def test_get_nested_key(self, temp_config_file):
        """Test getting nested key with dot notation"""
        config = Config(temp_config_file)
        assert config.get("platform.api_key") == "test-api-key"

    def test_get_list_item(self, temp_config_file):
        """Test getting list item with index"""
        config = Config(temp_config_file)
        assert config.get("devices.0.ip") == "192.168.1.101"
        assert config.get("devices.0.port") == 4370

    def test_get_nonexistent_with_default(self, temp_config_file):
        """Test getting nonexistent key returns default"""
        config = Config(temp_config_file)
        assert config.get("nonexistent") is None
        assert config.get("nonexistent", "default") == "default"
        assert config.get("platform.nonexistent", "default") == "default"

    def test_get_invalid_list_index(self, temp_config_file):
        """Test getting invalid list index returns default"""
        config = Config(temp_config_file)
        assert config.get("devices.999", "default") == "default"
        assert config.get("devices.-1", "default") == "default"

    def test_get_all(self, temp_config_file):
        """Test get_all returns full config"""
        config = Config(temp_config_file)
        all_config = config.get_all()
        assert "platform" in all_config
        assert "devices" in all_config
        assert all_config["platform"]["url"] == "https://test.example.com"


class TestConfigSave:
    """Tests for config saving"""

    def test_save_config(self, temp_config_file, tmp_path):
        """Test saving config to file"""
        config = Config(temp_config_file)
        output_path = tmp_path / "saved_config.yaml"
        config.save(output_path)

        # Reload and verify
        with open(output_path) as f:
            saved = yaml.safe_load(f)
        assert saved["platform"]["url"] == "https://test.example.com"
        assert saved["devices"][0]["ip"] == "192.168.1.101"

    def test_encrypt_sensitive_values(self, temp_config_file, encryption_key):
        """Test encrypt_sensitive_values method"""
        config = Config(temp_config_file, encryption_key=encryption_key)
        encrypted = config.encrypt_sensitive_values()

        # Check values are encrypted (not plain text)
        assert encrypted["platform"]["api_key"] != "test-api-key"
        assert encrypted["devices"][0]["password"] != "0"

        # Verify they can be decrypted
        fernet = Fernet(encryption_key.encode())
        decrypted_api = fernet.decrypt(encrypted["platform"]["api_key"].encode()).decode()
        assert decrypted_api == "test-api-key"

    def test_encrypt_without_key(self, temp_config_file):
        """Test encrypt_sensitive_values without key returns original"""
        config = Config(temp_config_file)
        encrypted = config.encrypt_sensitive_values()
        # Should return copy without encryption
        assert encrypted["platform"]["api_key"] == "test-api-key"


class TestConfigDotNotationEdgeCases:
    """Tests for edge cases in dot notation"""

    def test_get_with_numeric_keys_in_path(self, tmp_path):
        """Test getting values when path has numeric-like keys"""
        config_data = {
            "platform": {
                "url": "https://test.example.com",
                "api_key": "key",
                "tenant_id": "tenant",
            },
            "devices": [{"ip": "192.168.1.101", "123": "numeric_key"}],
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        config = Config(config_file)
        assert config.get("devices.0.123") == "numeric_key"

    def test_get_partial_path_on_list(self, temp_config_file):
        """Test getting partial path that ends on a list"""
        config = Config(temp_config_file)
        devices = config.get("devices")
        assert isinstance(devices, list)
        assert len(devices) == 1
