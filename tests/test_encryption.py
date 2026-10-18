"""
Unit tests for encryption module
"""
import os
import pytest

from src.security.encryption import (
    EncryptionError,
    decrypt_config_value,
    decrypt_value,
    derive_key,
    encrypt_config_value,
    encrypt_value,
    generate_key,
)


class TestEncryption:
    """Tests for encryption utilities"""

    def test_generate_key(self):
        """Test key generation returns valid base64 key"""
        key = generate_key()
        assert isinstance(key, str)
        assert len(key) > 0
        # Should be valid Fernet key
        from cryptography.fernet import Fernet
        f = Fernet(key.encode())
        assert f is not None

    def test_derive_key_with_salt(self):
        """Test key derivation with provided salt"""
        password = "test-password"
        salt = os.urandom(16)
        key, returned_salt = derive_key(password, salt)
        assert isinstance(key, str)
        assert returned_salt == salt
        assert len(key) > 0

    def test_derive_key_without_salt(self):
        """Test key derivation generates salt when not provided"""
        password = "test-password"
        key, salt = derive_key(password)
        assert isinstance(key, str)
        assert isinstance(salt, bytes)
        assert len(salt) == 16

    def test_derive_key_deterministic(self):
        """Test same password + salt produces same key"""
        password = "test-password"
        salt = os.urandom(16)
        key1, _ = derive_key(password, salt)
        key2, _ = derive_key(password, salt)
        assert key1 == key2

    def test_encrypt_decrypt_value(self):
        """Test encrypt and decrypt round-trip"""
        key = generate_key()
        original = "secret-value-123"
        encrypted = encrypt_value(original, key)
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == original
        assert encrypted != original

    def test_encrypt_decrypt_unicode(self):
        """Test encryption with unicode characters"""
        key = generate_key()
        original = "密码-пароль-🔐-café"
        encrypted = encrypt_value(original, key)
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == original

    def test_encrypt_decrypt_empty_string(self):
        """Test encryption with empty string"""
        key = generate_key()
        original = ""
        encrypted = encrypt_value(original, key)
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == original

    def test_encrypt_value_invalid_key(self):
        """Test encrypt with invalid key raises EncryptionError"""
        with pytest.raises(EncryptionError, match="Error encriptando"):
            encrypt_value("test", "invalid-key")

    def test_decrypt_value_invalid_key(self):
        """Test decrypt with invalid key raises EncryptionError"""
        with pytest.raises(EncryptionError, match="Error desencriptando"):
            decrypt_value("encrypted", "invalid-key")

    def test_decrypt_value_wrong_key(self):
        """Test decrypt with wrong key raises EncryptionError"""
        key1 = generate_key()
        key2 = generate_key()
        encrypted = encrypt_value("secret", key1)
        with pytest.raises(EncryptionError):
            decrypt_value(encrypted, key2)

    def test_decrypt_value_corrupted_data(self):
        """Test decrypt with corrupted data raises EncryptionError"""
        key = generate_key()
        with pytest.raises(EncryptionError):
            decrypt_value("corrupted-data", key)


class TestConfigEncryption:
    """Tests for config encryption helpers"""

    def test_encrypt_config_value_with_env_key(self):
        """Test encrypt_config_value uses ENCRYPTION_KEY from env"""
        key = generate_key()
        os.environ['ENCRYPTION_KEY'] = key
        try:
            original = "api-secret-key"
            encrypted = encrypt_config_value(original)
            assert encrypted != original
            # Should be decryptable
            decrypted = decrypt_value(encrypted, key)
            assert decrypted == original
        finally:
            del os.environ['ENCRYPTION_KEY']

    def test_decrypt_config_value_with_env_key(self):
        """Test decrypt_config_value uses ENCRYPTION_KEY from env"""
        key = generate_key()
        os.environ['ENCRYPTION_KEY'] = key
        try:
            original = "api-secret-key"
            encrypted = encrypt_value(original, key)
            decrypted = decrypt_config_value(encrypted)
            assert decrypted == original
        finally:
            del os.environ['ENCRYPTION_KEY']

    def test_encrypt_config_value_no_env_key(self, caplog):
        """Test encrypt_config_value without ENCRYPTION_KEY returns original"""
        if 'ENCRYPTION_KEY' in os.environ:
            del os.environ['ENCRYPTION_KEY']
        original = "plain-text"
        result = encrypt_config_value(original)
        assert result == original
        assert "ENCRYPTION_KEY no configurada" in caplog.text

    def test_decrypt_config_value_no_env_key(self, caplog):
        """Test decrypt_config_value without ENCRYPTION_KEY returns original"""
        if 'ENCRYPTION_KEY' in os.environ:
            del os.environ['ENCRYPTION_KEY']
        encrypted = "encrypted-value"
        result = decrypt_config_value(encrypted)
        assert result == encrypted
        assert "ENCRYPTION_KEY no configurada" in caplog.text

    def test_config_roundtrip_with_env(self):
        """Test full encrypt/decrypt cycle using env key"""
        key = generate_key()
        os.environ['ENCRYPTION_KEY'] = key
        try:
            original = "super-secret-api-key"
            encrypted = encrypt_config_value(original)
            decrypted = decrypt_config_value(encrypted)
            assert decrypted == original
        finally:
            del os.environ['ENCRYPTION_KEY']