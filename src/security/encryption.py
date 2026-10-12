"""
Utilidades de encriptación AES-256
"""

import os
import sys
import base64
import argparse
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Excepción para errores de encriptación"""
    pass


def generate_key() -> str:
    """
    Generar clave Fernet nueva
    
    Returns:
        str: Clave encriptada en base64
    """
    return Fernet.generate_key().decode()


def derive_key(password: str, salt: bytes = None) -> tuple:
    """
    Derivar clave desde password usando PBKDF2
    
    Args:
        password: Password original
        salt: Salt opcional (se genera si no se proporciona)
    
    Returns:
        tuple: (clave_derived, salt)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key.decode(), salt


def encrypt_value(value: str, key: str) -> str:
    """
    Encriptar un valor
    
    Args:
        value: Valor a encriptar
        key: Clave Fernet
    
    Returns:
        str: Valor encriptado en base64
    """
    try:
        fernet = Fernet(key.encode())
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Error encriptando: {e}")
        raise EncryptionError(f"Error encriptando: {e}")


def decrypt_value(encrypted_value: str, key: str) -> str:
    """
    Desencriptar un valor
    
    Args:
        encrypted_value: Valor encriptado en base64
        key: Clave Fernet
    
    Returns:
        str: Valor desencriptado
    """
    try:
        fernet = Fernet(key.encode())
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Error desencriptando: {e}")
        raise EncryptionError(f"Error desencriptando: {e}")


def encrypt_config_value(value: str) -> str:
    """
    Encriptar valor de configuración usando variable de ambiente
    
    Args:
        value: Valor a encriptar
    
    Returns:
        str: Valor encriptado
    """
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        logger.warning("ENCRYPTION_KEY no configurada, valor no encriptado")
        return value
    
    return encrypt_value(value, key)


def decrypt_config_value(encrypted_value: str) -> str:
    """
    Desencriptar valor de configuración usando variable de ambiente
    
    Args:
        encrypted_value: Valor encriptado
    
    Returns:
        str: Valor desencriptado
    """
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        logger.warning("ENCRYPTION_KEY no configurada, valor no desencriptado")
        return encrypted_value
    
    return decrypt_value(encrypted_value, key)


def main():
    """CLI para encriptar/desencriptar valores"""
    parser = argparse.ArgumentParser(description='Encrypt/decrypt config values using Fernet')
    parser.add_argument('action', choices=['encrypt', 'decrypt', 'generate-key'], help='Action to perform')
    parser.add_argument('value', nargs='?', help='Value to encrypt/decrypt (not needed for generate-key)')
    parser.add_argument('--key', help='Fernet key (or use ENCRYPTION_KEY env var)')
    
    args = parser.parse_args()
    
    if args.action == 'generate-key':
        print(generate_key())
        return
    
    key = args.key or os.environ.get('ENCRYPTION_KEY')
    if not key:
        print("ERROR: No key provided. Use --key or set ENCRYPTION_KEY env var")
        sys.exit(1)
    
    if args.action == 'encrypt':
        if not args.value:
            print("ERROR: Value required for encrypt action")
            sys.exit(1)
        print(encrypt_value(args.value, key))
    elif args.action == 'decrypt':
        if not args.value:
            print("ERROR: Value required for decrypt action")
            sys.exit(1)
        print(decrypt_value(args.value, key))


if __name__ == '__main__':
    main()
