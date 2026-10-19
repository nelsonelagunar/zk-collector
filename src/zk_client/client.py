"""
ZK Client - Wrapper para pyzk
Manejo de conexión y operaciones con dispositivos ZKTeco
"""

import logging
import time
from datetime import datetime
from typing import Any

from zk.exception import ZKError as PyZKError

from zk import ZK

from .attendance import AttendanceRecord
from .exceptions import ZKAttendanceError, ZKConnectionError

logger = logging.getLogger(__name__)


class ZKClient:
    """
    Cliente para dispositivos ZKTeco con:
    - Reconexión automática
    - Timeout configurable
    - Manejo de errores robusto
    - Logging detallado
    """

    def __init__(
        self,
        ip: str,
        port: int = 4370,
        timeout: int = 5,
        password: int = 0,
        force_udp: bool = False,
        ommit_ping: bool = False,
        encoding: str = "utf-8",
    ):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.password = password
        self.force_udp = force_udp
        self.ommit_ping = ommit_ping
        self.encoding = encoding

        self.zk: ZK | None = None
        self.connected = False
        self.last_connection_attempt: datetime | None = None
        self.last_successful_connection: datetime | None = None
        self.connection_attempts = 0
        self._device_info_cache: dict | None = None

    def connect(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        Establecer conexión con el dispositivo

        Args:
            max_retries: Número máximo de intentos
            retry_delay: Delay entre intentos (segundos)

        Returns:
            bool: True si conectó exitosamente
        """
        for attempt in range(1, max_retries + 1):
            self.last_connection_attempt = datetime.now()
            self.connection_attempts += 1

            try:
                logger.debug(f"Intentando conectar a {self.ip}:{self.port} (intento {attempt})")

                self.zk = ZK(
                    self.ip,
                    port=self.port,
                    timeout=self.timeout,
                    password=self.password,
                    force_udp=self.force_udp,
                    ommit_ping=self.ommit_ping,
                    encoding=self.encoding,
                )

                self.zk.connect()

                self.connected = True
                self.last_successful_connection = datetime.now()
                self.connection_attempts = 0  # Resetear contador

                logger.info(f"Conectado exitosamente a {self.ip}:{self.port}")
                return True

            except PyZKError as e:
                logger.warning(f"ZKError conectando a {self.ip}:{self.port}: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
            except ConnectionRefusedError as e:
                logger.error(f"Conexión rechazada por {self.ip}:{self.port}: {e}")
                raise ZKConnectionError(f"Conexión rechazada: {e}") from e
            except TimeoutError as e:
                logger.error(f"Timeout conectando a {self.ip}:{self.port}: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error inesperado conectando a {self.ip}:{self.port}: {e}")
                raise ZKConnectionError(f"Error inesperado: {e}") from e

        logger.error(
            f"No se pudo conectar a {self.ip}:{self.port} después de {max_retries} intentos"
        )
        self.connected = False
        return False

    def disconnect(self):
        """Cerrar conexión con el dispositivo"""
        if self.zk and self.connected:
            try:
                self.zk.disconnect()
                logger.info(f"Desconectado de {self.ip}:{self.port}")
            except Exception as e:
                logger.warning(f"Error cerrando conexión: {e}")
            finally:
                self.connected = False
                self.zk = None

    def get_attendance(
        self, clear_after_read: bool = False, disable_device: bool = True
    ) -> list[AttendanceRecord] | None:
        """
        Obtener registros de asistencia del dispositivo

        Args:
            clear_after_read: Si True, borra los registros después de leer
            disable_device: Si True, deshabilita el dispositivo durante la lectura

        Returns:
            Lista de AttendanceRecord o None si hay error
        """
        if not self.connected or not self.zk:
            logger.error("No hay conexión activa con el dispositivo")
            return None

        try:
            if disable_device:
                logger.debug(f"Deshabilitando dispositivo {self.ip}")
                self.zk.disable_device()

            logger.info(f"Obteniendo registros de asistencia de {self.ip}")
            attendances = self.zk.get_attendance()

            if not attendances:
                logger.warning(f"No hay registros de asistencia en {self.ip}")
                return []

            # Convertir a AttendanceRecord
            records = [
                AttendanceRecord.from_zk_attendance(attendance, self.ip)
                for attendance in attendances
            ]

            logger.info(f"Obtenidos {len(records)} registros de {self.ip}")

            if clear_after_read:
                logger.info(f"Limpiando registros de {self.ip}")
                self.zk.clear_attendance()

            return records

        except PyZKError as e:
            logger.error(f"ZKError obteniendo attendance: {e}")
            raise ZKAttendanceError(f"Error obteniendo attendance: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado obteniendo attendance: {e}")
            raise ZKAttendanceError(f"Error inesperado: {e}") from e
        finally:
            if disable_device:
                try:
                    self.zk.enable_device()
                    logger.debug(f"Dispositivo {self.ip} habilitado")
                except Exception as e:
                    logger.warning(f"Error habilitando dispositivo: {e}")

    def get_device_info(self) -> dict[str, Any] | None:
        """
        Obtener información del dispositivo

        Returns:
            Dict con información del dispositivo o None si hay error
        """
        if not self.connected or not self.zk:
            return None

        try:
            info = {
                "firmware_version": self.zk.get_firmware_version(),
                "serial_number": self.zk.get_serialnumber(),
                "platform": self.zk.get_platform(),
                "device_name": self.zk.get_device_name(),
                "mac_address": self.zk.get_mac(),
            }

            self._device_info_cache = info
            logger.debug(f"Información del dispositivo {self.ip}: {info}")

            return info

        except Exception as e:
            logger.error(f"Error obteniendo información del dispositivo: {e}")
            return None

    def get_users(self) -> list[dict] | None:
        """
        Obtener lista de usuarios del dispositivo

        Returns:
            Lista de usuarios o None si hay error
        """
        if not self.connected or not self.zk:
            return None

        try:
            users = self.zk.get_users()
            logger.info(f"Obtenidos {len(users)} usuarios de {self.ip}")
            return users if isinstance(users, list) else None
        except Exception as e:
            logger.error(f"Error obteniendo usuarios: {e}")
            return None

    def get_time(self) -> datetime | None:
        """
        Obtener hora actual del dispositivo

        Returns:
            datetime o None si hay error
        """
        if not self.connected or not self.zk:
            return None

        try:
            device_time = self.zk.get_time()
            logger.debug(f"Hora del dispositivo {self.ip}: {device_time}")
            return device_time if isinstance(device_time, datetime) else None
        except Exception as e:
            logger.error(f"Error obteniendo hora del dispositivo: {e}")
            return None

    def set_time(self, new_time: datetime) -> bool:
        """
        Establecer hora del dispositivo

        Args:
            new_time: Nueva hora a establecer

        Returns:
            bool: True si exitoso
        """
        if not self.connected or not self.zk:
            return False

        try:
            self.zk.set_time(new_time)
            logger.info(f"Hora del dispositivo {self.ip} actualizada")
            return True
        except Exception as e:
            logger.error(f"Error estableciendo hora: {e}")
            return False

    def restart(self) -> bool:
        """
        Reiniciar el dispositivo

        Returns:
            bool: True si exitoso
        """
        if not self.connected or not self.zk:
            return False

        try:
            self.zk.restart()
            logger.info(f"Dispositivo {self.ip} reiniciado")
            return True
        except Exception as e:
            logger.error(f"Error reiniciando dispositivo: {e}")
            return False

    def is_online(self) -> bool:
        """
        Verificar si el dispositivo está en línea

        Returns:
            bool: True si está conectado
        """
        if self.connected and self.zk:
            try:
                # Intentar obtener información básica
                self.zk.get_firmware_version()
                return True
            except Exception:
                self.connected = False
                return False
        return False

    def get_connection_status(self) -> dict[str, Any]:
        """
        Obtener estado de la conexión

        Returns:
            Dict con estado de conexión
        """
        attempt = self.last_connection_attempt
        success = self.last_successful_connection
        return {
            "ip": self.ip,
            "port": self.port,
            "connected": self.connected,
            "last_attempt": attempt.isoformat() if attempt else None,
            "last_success": success.isoformat() if success else None,
            "failed_attempts": self.connection_attempts,
        }
