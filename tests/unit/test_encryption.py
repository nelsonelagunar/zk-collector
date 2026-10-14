"""
Unit tests for Security Encryption
"""

import pytest

from src.security.encryption import (
    decrypt_value,
    derive_key,
    encrypt_value,
    generate_key,
)


class TestEncryption:
    """Tests for encryption module"""

    def test_generate_key(self):
        """Test key generation"""
        key = generate_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_encrypt_decrypt_value(self):
        """Test encrypt/decrypt value"""
        key = generate_key()
        data = "sensitive data"

        encrypted = encrypt_value(data, key)
        assert isinstance(encrypted, str)
        assert encrypted != data

        decrypted = decrypt_value(encrypted, key)
        assert decrypted == data

    def test_encrypt_different_each_time(self):
        """Test that encryption produces different output each time (non-deterministic)"""
        key = generate_key()
        data = "test data"

        encrypted1 = encrypt_value(data, key)
        encrypted2 = encrypt_value(data, key)

        assert encrypted1 != encrypted2
        # But both decrypt to same value
        assert decrypt_value(encrypted1, key) == data
        assert decrypt_value(encrypted2, key) == data

    def test_decrypt_wrong_key_fails(self):
        """Test that decrypt with wrong key fails"""
        key1 = generate_key()
        key2 = generate_key()
        data = "test data"

        encrypted = encrypt_value(data, key1)

        from src.security.encryption import EncryptionError
        with pytest.raises(EncryptionError):
            decrypt_value(encrypted, key2)

    def test_decrypt_corrupted_data_fails(self):
        """Test that decrypting corrupted data fails"""
        key = generate_key()
        data = "test data"

        encrypted = encrypt_value(data, key)
        # Corrupt the data
        corrupted = encrypted[:-1] + ('X' if encrypted[-1] != 'X' else 'Y')

        from src.security.encryption import EncryptionError
        with pytest.raises(EncryptionError):
            decrypt_value(corrupted, key)

    def test_derive_key(self):
        """Test key derivation from password"""
        password = "my_password"
        key, salt = derive_key(password)

        assert isinstance(key, str)
        assert isinstance(salt, bytes)
        assert len(salt) == 16

        # Same password + salt should produce same key
        key2, _ = derive_key(password, salt)
        assert key == key2
