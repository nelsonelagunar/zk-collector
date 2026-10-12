"""
Módulo de Configuración
Manejo de configuración YAML con encriptación AES-256
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List
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
        'platform': {
            'required': True,
            'fields': {
                'url': {'type': 'string', 'required': True},
                'api_key': {'type': 'string', 'required': True, 'sensitive': True},
                'tenant_id': {'type': 'string', 'required': True},
                'timeout': {'type': 'integer', 'default': 30},
                'retry_attempts': {'type': 'integer', 'default': 3},
            }
        },
        'devices': {
            'required': True,
            'type': 'list',
            'item_schema': {
                'ip': {'type': 'string', 'required': True},
                'port': {'type': 'integer', 'default': 4370},
                'timeout': {'type': 'integer', 'default': 5},
                'password': {'type': 'string', 'default': '0', 'sensitive': True},
                'name': {'type': 'string', 'default': ''},
                'enabled': {'type': 'boolean', 'default': True},
            }
        },
        'poll_interval_seconds': {
            'type': 'integer',
            'default': 300,
            'min': 60,
            'max': 3600
        },
        'sync_interval_seconds': {
            'type': 'integer',
            'default': 60,
            'min': 10,
            'max': 600
        },
        'buffer': {
            'required': False,
            'fields': {
                'max_records': {'type': 'integer', 'default': 10000},
                'cleanup_days': {'type': 'integer', 'default': 30},
                'db_path': {'type': 'string', 'default': ''},
            }
        },
        'logging': {
            'required': False,
            'fields': {
                'level': {
                    'type': 'string',
                    'default': 'INFO',
                    'allowed': ['DEBUG', 'INFO', 'WARNING', 'ERROR']
                },
                'max_size_mb': {'type': 'integer', 'default': 10},
                'backup_count': {'type': 'integer', 'default': 5},
                'format': {'type': 'string', 'default': 'text', 'allowed': ['text', 'json']},
            }
        }
    }
    
    def __init__(self, config_path: Path, encryption_key: Optional[str] = None):
        self.config_path = config_path
        self.encryption_key = encryption_key or os.environ.get('ENCRYPTION_KEY')
        self.config: Dict = {}
        self._load()
        self._validate()
    
    def _load(self):
        """Cargar configuración desde archivo YAML"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            
            self.config = raw_config
            
            # Desencriptar valores sensibles
            if self.encryption_key:
                self._decrypt_sensitive_values()
            
            # Aplicar valores por defecto del schema
            self._apply_defaults()
            
        except FileNotFoundError:
            raise ConfigError(f"Archivo no encontrado: {self.config_path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parseando YAML: {e}")
        except Exception as e:
            raise ConfigError(f"Error cargando configuración: {e}")
    
    def _decrypt_sensitive_values(self):
        """Desencriptar valores sensibles"""
        fernet = Fernet(self.encryption_key.encode())
        
        # Platform API Key
        if 'platform' in self.config and 'api_key' in self.config['platform']:
            try:
                encrypted = self.config['platform']['api_key']
                decrypted = fernet.decrypt(encrypted.encode()).decode()
                self.config['platform']['api_key'] = decrypted
            except Exception as e:
                logger.warning(f"No se pudo desencriptar api_key: {e}")
        
        # Device passwords
        if 'devices' in self.config:
            for device in self.config['devices']:
                if 'password' in device and device['password']:
                    try:
                        encrypted = device['password']
                        # Only decrypt if it looks encrypted (base64 format)
                        if self._looks_encrypted(encrypted):
                            decrypted = fernet.decrypt(encrypted.encode()).decode()
                            device['password'] = decrypted
                    except Exception as e:
                        logger.warning(f"No se pudo desencriptar password del dispositivo {device.get('ip', 'unknown')}: {e}")
    
    def _looks_encrypted(self, value: str) -> bool:
        """Check if a value looks like it's Fernet encrypted (base64, ~44 chars)"""
        if not isinstance(value, str):
            return False
        # Fernet tokens are base64 encoded, typically 44 chars or multiples
        try:
            import base64
            decoded = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
            return len(decoded) >= 32  # Fernet tokens are at least 32 bytes
        except Exception:
            return False
    
    def _apply_defaults(self):
        """Aplicar valores por defecto del schema"""
        for section, schema in self.SCHEMA.items():
            if section not in self.config:
                if schema.get('required', False):
                    raise ConfigError(f"Sección requerida faltante: {section}")
                continue
            
            if 'fields' in schema:
                for field, field_schema in schema['fields'].items():
                    if field not in self.config[section]:
                        if 'default' in field_schema:
                            self.config[section][field] = field_schema['default']
            
            # Apply defaults for list items
            if schema.get('type') == 'list' and 'item_schema' in schema:
                for item in self.config[section]:
                    for field, field_schema in schema['item_schema'].items():
                        if field not in item and 'default' in field_schema:
                            item[field] = field_schema['default']
    
    def _validate(self):
        """Validar configuración contra schema"""
        # Validaciones básicas
        if 'platform' not in self.config:
            raise ConfigError("Sección 'platform' es requerida")
        
        if 'devices' not in self.config:
            raise ConfigError("Sección 'devices' es requerida")
        
        if not self.config['devices']:
            raise ConfigError("Al menos un dispositivo debe estar configurado")
        
        # Validar URLs
        platform_url = self.config['platform'].get('url', '')
        if not platform_url.startswith(('http://', 'https://')):
            raise ConfigError("platform.url debe ser una URL válida")
        
        # Validar IPs de dispositivos
        import re
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        for i, device in enumerate(self.config['devices']):
            if not ip_pattern.match(device.get('ip', '')):
                raise ConfigError(f"Dispositivo {i+1}: IP inválida")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtener valor de configuración usando notación dot
        
        Ejemplo:
            config.get('platform.url')
            config.get('devices.0.ip')
        """
        keys = key.split('.')
        value = self.config
        
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
    
    def get_all(self) -> Dict:
        """Obtener toda la configuración"""
        return self.config.copy()
    
    def save(self, output_path: Optional[Path] = None):
        """Guardar configuración a archivo"""
        path = output_path or self.config_path
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Configuración guardada: {path}")
    
    def encrypt_sensitive_values(self) -> Dict:
        """
        Encriptar valores sensibles para guardar en archivo
        
        Returns:
            Dict con valores encriptados
        """
        if not self.encryption_key:
            logger.warning("ENCRYPTION_KEY no configurada, no se encriptarán valores")
            return self.config.copy()
        
        fernet = Fernet(self.encryption_key.encode())
        encrypted_config = self.config.copy()
        
        # Encriptar platform.api_key
        if 'platform' in encrypted_config and 'api_key' in encrypted_config['platform']:
            api_key = encrypted_config['platform']['api_key']
            if api_key and not self._looks_encrypted(api_key):
                encrypted_config['platform']['api_key'] = fernet.encrypt(api_key.encode()).decode()
        
        # Encriptar device passwords
        if 'devices' in encrypted_config:
            for device in encrypted_config['devices']:
                if 'password' in device and device['password']:
                    password = str(device['password'])
                    if password and not self._looks_encrypted(password):
                        device['password'] = fernet.encrypt(password.encode()).decode()
        
        return encrypted_config
