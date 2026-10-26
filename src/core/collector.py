"""
Attendance Collector - Orquestador principal
"""

import logging
import os
import time
from datetime import datetime
from typing import Any

from src.buffer.repository import BufferRepository
from src.core.config import Config
from src.monitoring.health import HealthMonitor
from src.sync.platform import PlatformSync
from src.zk_client.client import ZKClient

logger = logging.getLogger(__name__)


class AttendanceCollector:
    """
    Orquestador principal del colector de asistencia

    Responsabilidades:
    - Coordinar polling de dispositivos
    - Gestionar buffer local
    - Sincronizar con plataforma
    - Monitoreo de salud
    """

    def __init__(self, config: Config):
        self.config = config
        self.running = False

        # Inicializar componentes
        self.buffer = BufferRepository(
            db_path=self.config.get(
                "buffer.db_path",
                os.environ.get("BUFFER_DB_PATH", "/opt/attendance/data/buffer.db"),
            ),
            max_records=self.config.get("buffer.max_records", 10000),
        )

        self.platform_sync = PlatformSync(
            platform_url=self.config.get("platform.url"),
            api_key=self.config.get("platform.api_key"),
            tenant_id=self.config.get("platform.tenant_id"),
            timeout=self.config.get("platform.timeout", 30),
            retry_attempts=self.config.get("platform.retry_attempts", 3),
        )

        self.health_monitor = HealthMonitor(
            platform_sync=self.platform_sync,
            interval=self.config.get("health.heartbeat_interval", 300),
        )

        # Configuración de intervalos
        self.poll_interval = self.config.get("poll_interval_seconds", 300)
        self.sync_interval = self.config.get("sync_interval_seconds", 60)

        # Dispositivos
        self.devices_config = self.config.get("devices", [])
        self.zk_clients: dict[str, ZKClient] = {}
        # Huso por dispositivo (MYK-420): device.timezone -> config timezone
        # global; None deja que el buffer localice con su default.
        self.client_timezones: dict[str, Any] = {}

        # Estado
        self.last_poll: datetime | None = None
        self.last_sync: datetime | None = None
        self.last_heartbeat: datetime | None = None

        logger.info("AttendanceCollector inicializado")

    def _initialize_devices(self):
        """Inicializar clientes para cada dispositivo"""
        for device in self.devices_config:
            if not device.get("enabled", True):
                logger.info(f"Dispositivo deshabilitado: {device.get('ip')}")
                continue

            ip = device.get("ip")
            client = ZKClient(
                ip=ip,
                port=device.get("port", 4370),
                timeout=device.get("timeout", 5),
                password=device.get("password", 0),
                ommit_ping=device.get("ommit_ping", False),
            )
            self.zk_clients[ip] = client
            self.client_timezones[ip] = device.get("timezone") or self.config.get("timezone")
            logger.info(f"Dispositivo configurado: {ip}")

    def poll_devices(self):
        """Polling de todos los dispositivos configurados"""
        logger.info("Iniciando polling de dispositivos...")

        success_count = 0
        error_count = 0

        for ip, client in self.zk_clients.items():
            logger.info(f"Polling dispositivo {ip}")

            try:
                # Conectar
                if not client.connect(max_retries=3, retry_delay=2.0):
                    logger.error(f"No se pudo conectar a {ip}")
                    error_count += 1
                    continue

                # Obtener registros
                attendances = client.get_attendance(
                    clear_after_read=False,
                    disable_device=True,
                    timezone=self.client_timezones.get(ip),
                )

                if attendances:
                    # Guardar en buffer
                    self.buffer.add_records(attendances)
                    logger.info(f"{len(attendances)} registros de {ip} guardados en buffer")
                    success_count += 1
                else:
                    logger.info(f"No hay registros en {ip}")

                # Desconectar
                client.disconnect()

            except Exception as e:
                logger.error(f"Error polling {ip}: {e}", exc_info=True)
                error_count += 1
                if client.connected:
                    client.disconnect()

        self.last_poll = datetime.now()
        logger.info(f"Polling completado: {success_count} exitosos, {error_count} fallidos")

    def sync_to_platform(self):
        """Sincronizar buffer con plataforma"""
        logger.info("Iniciando sincronización con plataforma...")

        start_time = time.time()

        # Obtener registros pendientes
        unsynced = self.buffer.get_unsynced_records(limit=1000)

        if not unsynced:
            logger.info("No hay registros pendientes de sincronizar")
            self.buffer.log_sync(0, 0, "success", duration_seconds=0)
            return

        # Sincronizar
        success = self.platform_sync.sync_attendance(unsynced)

        duration = time.time() - start_time

        if success:
            # Marcar como sincronizados
            record_ids = [r["id"] for r in unsynced]
            self.buffer.mark_as_synced(record_ids)
            self.buffer.log_sync(
                records_synced=len(unsynced),
                records_failed=0,
                status="success",
                duration_seconds=duration,
            )
            logger.info(f"Sincronización completada: {len(unsynced)} registros en {duration:.2f}s")
        else:
            # Marcar como fallido
            record_ids = [r["id"] for r in unsynced]
            self.buffer.mark_sync_failed(record_ids)
            self.buffer.log_sync(
                records_synced=0,
                records_failed=len(unsynced),
                status="failed",
                error_message="Platform error",
                duration_seconds=duration,
            )
            logger.error("Sincronización fallida")

        self.last_sync = datetime.now()

    def run(self):
        """Loop principal del colector"""
        logger.info("=" * 60)
        logger.info("Attendance Collector Iniciado")
        logger.info(f"Dispositivos configurados: {len(self.zk_clients)}")
        logger.info(f"Plataforma: {self.config.get('platform.url')}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(f"Sync interval: {self.sync_interval}s")
        logger.info("=" * 60)

        # Inicializar dispositivos
        self._initialize_devices()

        # Iniciar health monitor
        self.health_monitor.start()

        self.running = True

        try:
            while self.running:
                time.time()

                # Polling de dispositivos
                if self._should_run(self.last_poll, self.poll_interval):
                    self.poll_devices()
                    self.last_poll = datetime.now()

                # Sincronización con plataforma (sync_local si está deshabilitada)
                if self.config.get("sync_enabled", True) and self._should_run(
                    self.last_sync, self.sync_interval
                ):
                    self.sync_to_platform()
                    self.last_sync = datetime.now()

                # Sleep corto para no bloquear
                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Interrupción por teclado")
        except Exception as e:
            logger.error(f"Error en loop principal: {e}", exc_info=True)
            raise
        finally:
            self.stop()

    def _should_run(self, last_run: datetime | None, interval: int) -> bool:
        """Verificar si es hora de ejecutar una tarea"""
        if last_run is None:
            return True

        elapsed = (datetime.now() - last_run).total_seconds()
        return elapsed >= interval

    def stop(self):
        """Detener el colector"""
        logger.info("Deteniendo Attendance Collector...")

        self.running = False

        # Detener health monitor
        self.health_monitor.stop()

        # Desconectar todos los dispositivos
        for client in self.zk_clients.values():
            if client.connected:
                client.disconnect()

        logger.info("Attendance Collector detenido")
