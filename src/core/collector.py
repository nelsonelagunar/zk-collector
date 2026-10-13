"""
Attendance Collector - Orquestador principal
"""

import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from src.buffer.repository import BufferRepository
from src.core.config import Config
from src.core.constants import DEFAULT_DATA_DIR
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

    # Cache TTL for devices from WebGUI DB (seconds)
    DEVICES_CACHE_TTL = 60

    def __init__(self, config: Config, webgui_db_path: str | None = None):
        self.config = config
        self.running = False

        # WebGUI DB path (for device source of truth)
        self.webgui_db_path = webgui_db_path or os.environ.get(
            "WEBGUI_DB_PATH", DEFAULT_DATA_DIR + "/webgui.db"
        )

        # Inicializar componentes
        # Use config value or fallback to env var via constants
        buffer_db_path = (
            self.config.get("buffer.db_path")
            or os.environ.get("BUFFER_DB_PATH")
            or DEFAULT_DATA_DIR + "/buffer.db"
        )
        self.buffer = BufferRepository(
            db_path=Path(buffer_db_path), max_records=self.config.get("buffer.max_records", 10000)
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

        # Dispositivos - cache
        self._devices_cache: list[dict] | None = None
        self._devices_cache_timestamp: float | None = None
        self.zk_clients: dict[str, ZKClient] = {}

        # Estado
        self.last_poll: datetime | None = None
        self.last_sync: datetime | None = None
        self.last_heartbeat: datetime | None = None

        logger.info("AttendanceCollector inicializado")
        logger.info(f"WebGUI DB path: {self.webgui_db_path}")

    def _load_devices_from_webgui_db(self) -> list[dict]:
        """
        Cargar dispositivos habilitados desde la WebGUI DB (SQLite).

        Returns:
            Lista de dicts con: ip, port, timeout, password, name, enabled
        """
        if not os.path.exists(self.webgui_db_path):
            logger.warning(f"WebGUI DB no existe: {self.webgui_db_path}")
            return []

        try:
            conn = sqlite3.connect(self.webgui_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ip, port, password, timeout, name
                FROM devices
                WHERE enabled = 1
            """)

            devices = []
            for row in cursor.fetchall():
                devices.append({
                    "ip": row["ip"],
                    "port": row["port"] if row["port"] else 4370,
                    "timeout": row["timeout"] if row["timeout"] else 5,
                    "password": row["password"] if row["password"] else "0",
                    "name": row["name"] if row["name"] else "Unknown",
                    "enabled": True,
                })

            conn.close()
            logger.info(f"Cargados {len(devices)} dispositivos desde WebGUI DB")
            return devices

        except sqlite3.Error as e:
            logger.error(f"Error leyendo WebGUI DB: {e}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado leyendo WebGUI DB: {e}")
            return []

    def _get_devices_with_cache(self) -> list[dict]:
        """
        Obtener dispositivos con cache TTL de 60s.

        Returns:
            Lista de dispositivos (desde cache o WebGUI DB)
        """
        now = time.time()

        # Check cache validity
        if (
            self._devices_cache is not None
            and self._devices_cache_timestamp is not None
            and (now - self._devices_cache_timestamp) < self.DEVICES_CACHE_TTL
        ):
            logger.debug("Usando devices cacheados")
            return self._devices_cache

        # Cache miss or expired - load from WebGUI DB
        logger.debug("Cache miss/expirado - cargando desde WebGUI DB")
        devices = self._load_devices_from_webgui_db()

        # Fallback to collector.yaml if WebGUI DB has no devices
        if not devices:
            logger.info("WebGUI DB sin dispositivos, usando collector.yaml como fallback")
            devices = self.config.get("devices", [])

        self._devices_cache = devices
        self._devices_cache_timestamp = now
        return devices

    def _initialize_devices(self):
        """Inicializar clientes para cada dispositivo desde WebGUI DB"""
        devices = self._get_devices_with_cache()

        if not devices:
            logger.warning("No hay dispositivos configurados para polling")
            return

        for device in devices:
            if not device.get("enabled", True):
                logger.info(f"Dispositivo deshabilitado: {device.get('ip')}")
                continue

            ip = device.get("ip")
            if ip in self.zk_clients:
                # Device already initialized, skip
                continue

            client = ZKClient(
                ip=ip,
                port=device.get("port", 4370),
                timeout=device.get("timeout", 5),
                password=device.get("password", 0),
            )
            self.zk_clients[ip] = client
            logger.info(f"Dispositivo configurado: {ip} ({device.get('name', 'Unknown')})")

    def _sync_device_clients(self):
        """
        Sincronizar clientes ZK con la lista actual de dispositivos.
        - Agrega nuevos dispositivos
        - Desconecta y remueve dispositivos que ya no están en la DB o están deshabilitados
        """
        # Get current device IPs from WebGUI DB (with cache)
        current_devices = self._get_devices_with_cache()
        current_ips = {d["ip"] for d in current_devices if d.get("enabled", True)}

        # Remove clients for devices no longer in DB or disabled
        ips_to_remove = set(self.zk_clients.keys()) - current_ips
        for ip in ips_to_remove:
            client = self.zk_clients[ip]
            if client.connected:
                client.disconnect()
            del self.zk_clients[ip]
            logger.info(f"Dispositivo removido del polling: {ip}")

        # Add new clients for devices not yet initialized
        for device in current_devices:
            if not device.get("enabled", True):
                continue

            ip = device.get("ip")
            if ip not in self.zk_clients:
                client = ZKClient(
                    ip=ip,
                    port=device.get("port", 4370),
                    timeout=device.get("timeout", 5),
                    password=device.get("password", 0),
                )
                self.zk_clients[ip] = client
                logger.info(
                    f"Nuevo dispositivo agregado al polling: {ip} "
                    f"({device.get('name', 'Unknown')})"
                )

    def poll_devices(self):
        """Polling de todos los dispositivos configurados"""
        logger.info("Iniciando polling de dispositivos...")

        # Refresh device clients from WebGUI DB (cache TTL 60s)
        self._initialize_devices()
        self._sync_device_clients()

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
                attendances = client.get_attendance(clear_after_read=False, disable_device=True)

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

                # Sincronización con plataforma
                if self._should_run(self.last_sync, self.sync_interval):
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
