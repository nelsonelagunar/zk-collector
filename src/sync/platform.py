"""
Cliente HTTP para sincronización con plataforma SaaS
"""

import logging
from datetime import datetime
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class PlatformSync:
    """
    Cliente para sincronización con plataforma SaaS

    Características:
    - HTTPS con autenticación JWT/API Key
    - Reintentos automáticos con backoff exponencial
    - Timeout configurable
    - Compresión gzip para payloads grandes
    """

    def __init__(
        self,
        platform_url: str,
        api_key: str,
        tenant_id: str,
        timeout: int = 30,
        retry_attempts: int = 3
    ):
        self.platform_url = platform_url.rstrip('/')
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.timeout = timeout

        # Configurar sesión con reintentos
        self.session = requests.Session()

        # Retry strategy
        retry_strategy = Retry(
            total=retry_attempts,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Headers por defecto
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'X-Tenant-ID': tenant_id,
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
        })

        logger.info(f"PlatformSync inicializado: {self.platform_url}")

    def sync_attendance(self, records: list[dict]) -> bool:
        """
        Sincronizar registros de asistencia con plataforma

        Args:
            records: Lista de registros a sincronizar

        Returns:
            bool: True si exitoso
        """
        if not records:
            return True

        endpoint = f"{self.platform_url}/api/v1/attendance/sync"

        logger.info(f"Sincronizando {len(records)} registros a {endpoint}")

        try:
            # Preparar payload
            payload = {
                'records': [
                    {
                        'user_id': r['user_id'],
                        'timestamp': r['timestamp'],
                        'status': r['status'],
                        'device_ip': r['device_ip'],
                        'punch_type': r.get('punch_type', 'unknown')
                    }
                    for r in records
                ],
                'synced_at': datetime.now().isoformat(),
                'collector_version': '1.0.0'
            }

            # Enviar request
            response = self.session.post(
                endpoint,
                json=payload,
                timeout=self.timeout
            )

            # Verificar respuesta
            response.raise_for_status()

            logger.info(f"Sincronización exitosa: {len(records)} registros")
            return True

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout sincronizando: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de conexión: {e}")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP: {e} - Status: {response.status_code}")
            if response.status_code == 401:
                logger.error("API Key inválida o expirada")
            elif response.status_code == 404:
                logger.error("Endpoint no encontrado")
            return False
        except Exception as e:
            logger.error(f"Error inesperado sincronizando: {e}", exc_info=True)
            return False

    def send_heartbeat(
        self,
        metrics: dict[str, Any],
        devices_status: list[dict[str, Any]]
    ) -> bool:
        """
        Enviar heartbeat a plataforma

        Args:
            metrics: Métricas del sistema (RAM, CPU, disco, buffer)
            devices_status: Estado de dispositivos conectados

        Returns:
            bool: True si exitoso
        """
        endpoint = f"{self.platform_url}/api/v1/collector/heartbeat"

        payload = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'metrics': metrics,
            'devices': devices_status
        }

        try:
            response = self.session.post(
                endpoint,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.debug("Heartbeat enviado exitosamente")
            return True
        except Exception as e:
            logger.error(f"Error enviando heartbeat: {e}")
            return False

    def get_config(self) -> dict[str, Any] | None:
        """
        Obtener configuración desde plataforma

        Returns:
            Dict con configuración o None si hay error
        """
        endpoint = f"{self.platform_url}/api/v1/collector/config"

        try:
            response = self.session.get(endpoint, timeout=10)
            response.raise_for_status()
            config: dict[str, Any] = response.json()
            logger.info("Configuración obtenida de plataforma")
            return config
        except Exception as e:
            logger.error(f"Error obteniendo configuración: {e}")
            return None

    def check_version(self) -> str | None:
        """
        Verificar versión disponible en plataforma

        Returns:
            Versión disponible o None
        """
        endpoint = f"{self.platform_url}/api/v1/collector/version"

        try:
            response = self.session.get(endpoint, timeout=10)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            version = data.get('latest_version')
            logger.debug(f"Versión disponible: {version}")
            return version
        except Exception as e:
            logger.error(f"Error verificando versión: {e}")
            return None

    def download_update(self, version: str) -> bytes | None:
        """
        Descargar actualización

        Args:
            version: Versión a descargar

        Returns:
            Binario de actualización o None
        """
        endpoint = f"{self.platform_url}/api/v1/collector/download/{version}"

        try:
            response = self.session.get(endpoint, timeout=300)
            response.raise_for_status()
            logger.info(f"Actualización descargada: {version}")
            content: bytes = response.content
            return content
        except Exception as e:
            logger.error(f"Error descargando actualización: {e}")
            return None

    def report_error(self, error_type: str, error_message: str, context: dict) -> bool:
        """
        Reportar error a plataforma

        Args:
            error_type: Tipo de error
            error_message: Mensaje de error
            context: Contexto adicional

        Returns:
            bool: True si exitoso
        """
        endpoint = f"{self.platform_url}/api/v1/collector/error"

        payload = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message,
            'context': context,
            'version': '1.0.0'
        }

        try:
            response = self.session.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error reportando error: {e}")
            return False
