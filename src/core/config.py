"""
Módulo de Configuración
Manejo de configuración YAML con encriptación AES-256
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Excepción para errores de configuración"""

    pass


class Config:
    """
    Manejador de configuración con soporte para:
    - YAML files
    - Variables de ambiente
    - Encriptación AES-256
    - Validación de schema
    """

    SCHEMA = {
        "platform": {
            "required": True,
            "fields": {
                "url": {"type": "string", "required": True},
                "api_key": {"type": "string", "required": True, "sensitive": True},
                "tenant_id": {"type": "string", "required": True},
                "timeout": {"type": "integer", "default": 30},
                "retry_attempts": {"type": "integer", "default": 3},
            },
        },
        "devices": {
            "required": True,
            "type": "list",
            "item_schema": {
                "ip": {"type": "string", "required": True},
                "port": {"type": "integer", "default": 4370},
                "timeout": {"type": "integer", "default": 5},
                "password": {"type": "integer", "default": 0},
                "name": {"type": "string", "default": ""},
                "enabled": {"type": "boolean", "default": True},
                # Skip pyzk ICMP/TCP ping. Required for the mock ZK emulator
                # (mock/zk_emulator.py) which only implements the ZK TCP protocol.
                "ommit_ping": {"type": "boolean", "default": False},
            },
        },
        "poll_interval_seconds": {"type": "integer", "default": 300, "min": 60, "max": 3600},
        "sync_interval_seconds": {"type": "integer", "default": 60, "min": 10, "max": 600},
        "clock_sync": {
            "required": False,
            "fields": {
                # MYK-421 (MYK-410 TZ-1): deriva máxima tolerada del reloj del
                # dispositivo (segundos) antes de corregir con set_time() + alerta.
                "threshold_seconds": {"type": "integer", "default": 60, "min": 1},
            },
        },
        "buffer": {
            "required": False,
            "fields": {
                "max_records": {"type": "integer", "default": 10000},
                # MYK-419 / RT-1 (LFT 804-III): retención legal 26 meses
                # (~790 días). El borrado es manual y solo tras archivo previo.
                "retention_days": {"type": "integer", "default": 790},
                # Directorio donde se exporta (archiva) antes de purgar.
                "archive_dir": {"type": "string", "default": None},
            },
        },
        "logging": {
            "required": False,
            "fields": {
                "level": {
                    "type": "string",
                    "default": "INFO",
                    "allowed": ["DEBUG", "INFO", "WARNING", "ERROR"],
                },
                "max_size_mb": {"type": "integer", "default": 10},
                "backup_count": {"type": "integer", "default": 5},
            },
        },
    }

    def __init__(self, config_path: Path, encryption_key: str | None = None):
        self.config_path: Path | None = config_path
        self.encryption_key = encryption_key or os.environ.get("ENCRYPTION_KEY")
        self.config: dict = {}
        self._load()
        self._validate()

    @classmethod
    def default(cls) -> "Config":
        """Config mínima por defecto cuando collector.yaml no existe.

        Post-MYK-172 los devices se leen desde la DB del WebGUI (una sola fuente
        de verdad). Este default permite arrancar el collector con 0 devices sin
        fallar mientras la fuente real es la DB.
        """
        cfg = cls.__new__(cls)
        cfg.config_path = None
        cfg.encryption_key = os.environ.get("ENCRYPTION_KEY")
        cfg.config = {
            "devices": [],
            "platform": {"url": "", "api_key": "", "tenant_id": ""},
            "poll_interval_seconds": 300,
            "sync_interval_seconds": 60,
            "sync_enabled": False,
            "buffer": {"max_records": 10000, "retention_days": 790},
            "logging": {"level": "INFO"},
        }
        return cfg

    def _load(self):
        """Cargar configuración desde archivo YAML"""
        if self.config_path is None:
            # Config en memoria (p.ej. Config.default()): no hay archivo que cargar.
            return
        try:
            with open(self.config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            self.config = raw_config

            # Desencriptar valores sensibles
            if self.encryption_key:
                self._decrypt_sensitive_values()

            # Aplicar valores por defecto del schema
            self._apply_defaults()

        except FileNotFoundError as e:
            raise ConfigError(f"Archivo no encontrado: {self.config_path}") from e
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parseando YAML: {e}") from e
        except Exception as e:
            raise ConfigError(f"Error cargando configuración: {e}") from e

    def _decrypt_sensitive_values(self):
        """Desencriptar valores sensibles"""
        fernet = Fernet(self.encryption_key.encode())

        # Platform API Key
        if "platform" in self.config and "api_key" in self.config["platform"]:
            try:
                encrypted = self.config["platform"]["api_key"]
                decrypted = fernet.decrypt(encrypted.encode()).decode()
                self.config["platform"]["api_key"] = decrypted
            except Exception as e:
                logger.warning(f"No se pudo desencriptar api_key: {e}")

    def _apply_defaults(self):
        """Aplicar valores por defecto del schema"""
        for section, schema in self.SCHEMA.items():
            if section not in self.config:
                if schema.get("required", False):
                    raise ConfigError(f"Sección requerida faltante: {section}")
                continue

            if "fields" in schema:
                for field, field_schema in schema["fields"].items():
                    if field not in self.config[section] and "default" in field_schema:
                        self.config[section][field] = field_schema["default"]

    def _validate(self):
        """Validar configuración contra schema"""
        # Validaciones básicas
        if "platform" not in self.config:
            raise ConfigError("Sección 'platform' es requerida")

        if "devices" not in self.config:
            raise ConfigError("Sección 'devices' es requerida")

        if not self.config["devices"]:
            raise ConfigError("Al menos un dispositivo debe estar configurado")

        # Validar URLs
        platform_url = self.config["platform"].get("url", "")
        if not platform_url.startswith(("http://", "https://")):
            raise ConfigError("platform.url debe ser una URL válida")

        # Validar IPs de dispositivos
        import re

        ip_pattern = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
        for i, device in enumerate(self.config["devices"]):
            if not ip_pattern.match(device.get("ip", "")):
                raise ConfigError(f"Dispositivo {i + 1}: IP inválida")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtener valor de configuración usando notación dot

        Ejemplo:
            config.get('platform.url')
            config.get('devices.0.ip')
        """
        keys = key.split(".")
        value: Any = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            elif isinstance(value, list):
                try:
                    index = int(k)
                    value = value[index] if 0 <= index < len(value) else default
                except (ValueError, IndexError):
                    return default
            else:
                return default

        return value

    def get_all(self) -> dict:
        """Obtener toda la configuración"""
        return self.config.copy()

    def save(self, output_path: Path | None = None):
        """Guardar configuración a archivo"""
        path = output_path or self.config_path
        if path is None:
            raise ConfigError("No hay ruta de configuración (config_path es None)")

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Configuración guardada: {path}")
