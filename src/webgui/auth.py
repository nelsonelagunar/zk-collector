"""
Auth Module - Authentication & Authorization
Manejo de autenticación con JWT y Argon2id
"""

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Excepción para errores de autenticación"""

    pass


class Auth:
    """
    Sistema de autenticación con:
    - Hash de contraseñas con Argon2id
    - JWT tokens con expiración
    - Refresh tokens rotativos
    """

    def __init__(self, secret_key: str | None = None):
        self.secret_key = secret_key or os.environ.get("WEBGUI_SECRET_KEY", secrets.token_hex(32))
        self.ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32)
        self.token_expiry_minutes = 30
        self.refresh_token_days = 7

    def hash_password(self, password: str) -> str:
        """Hashear contraseña con Argon2id"""
        return self.ph.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verificar contraseña contra hash"""
        try:
            self.ph.verify(password_hash, password)
            return True
        except VerifyMismatchError:
            return False

    def generate_tokens(self, user_id: int, username: str, role: str) -> dict[str, str]:
        """Generar access token y refresh token"""
        now = datetime.utcnow()

        # Access token (corta duración)
        access_payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": now + timedelta(minutes=self.token_expiry_minutes),
            "iat": now,
            "type": "access",
        }
        access_token = jwt.encode(access_payload, self.secret_key, algorithm="HS256")

        # Refresh token (larga duración)
        refresh_payload = {
            "user_id": user_id,
            "exp": now + timedelta(days=self.refresh_token_days),
            "iat": now,
            "type": "refresh",
            "jti": secrets.token_hex(16),  # Unique ID para el token
        }
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm="HS256")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": str(self.token_expiry_minutes * 60),
        }

    def verify_access_token(self, token: str) -> dict | None:
        """Verificar access token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Token inválido: {e}")
            return None

    def verify_refresh_token(self, token: str) -> dict | None:
        """Verificar refresh token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            if payload.get("type") != "refresh":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Refresh token expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Refresh token inválido: {e}")
            return None

    def rotate_tokens(
        self,
        refresh_token: str,
        user_id: int,
        username: str,
        role: str,
    ) -> dict[str, str] | None:
        """Rotar tokens - invalida el refresh token anterior"""
        # Verificar refresh token actual
        payload = self.verify_refresh_token(refresh_token)
        if not payload:
            return None

        # Generar nuevos tokens
        return self.generate_tokens(user_id, username, role)

    @staticmethod
    def generate_password_reset_token() -> str:
        """Generar token para reset de contraseña"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, list[str]]:
        """
        Validar fortaleza de contraseña

        Returns:
            Tuple[bool, List[str]]: (es_valida, lista_de_errores)
        """
        errors = []

        if len(password) < 12:
            errors.append("Mínimo 12 caracteres")

        if not any(c.isupper() for c in password):
            errors.append("Al menos una mayúscula")

        if not any(c.islower() for c in password):
            errors.append("Al menos una minúscula")

        if not any(c.isdigit() for c in password):
            errors.append("Al menos un número")

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Al menos un carácter especial")

        return len(errors) == 0, errors

    @staticmethod
    def hash_reset_token(token: str) -> str:
        """Hash del token de reset para almacenamiento seguro (SHA256)"""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def verify_reset_token(token: str, token_hash: str) -> bool:
        """Verificar token de reset contra su hash (comparación en tiempo constante)"""
        expected_hash = hashlib.sha256(token.encode()).hexdigest()
        return hmac.compare_digest(expected_hash, token_hash)

    def generate_reset_token_and_hash(self) -> tuple[str, str]:
        """Generar token de reset y su hash para almacenamiento

        Returns:
            Tuple[str, str]: (token_plano, token_hash)
        """
        token = self.generate_password_reset_token()
        token_hash = self.hash_reset_token(token)
        return token, token_hash
