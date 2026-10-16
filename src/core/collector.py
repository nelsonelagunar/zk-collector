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
            db_path=self.config.get('buffer.db_path', '/opt/attendance/data/buffer.db'),
            max_records=self.config.get('buffer.max_records', 10000)
        )

        self.platform_sync = PlatformSync(
            platform_url=self.config.get('platform.url'),
            api_key=self.config.get('platform.api_key'),
            tenant_id=self.config.get('platform.tenant_id'),
            timeout=self.config.get('platform.timeout', 30),
            retry_attempts=self.config.get('platform.retry_attempts', 3)
        )

        self.health_monitor = HealthMonitor(
            platform_sync=self.platform_sync,
            interval=self.config.get('health.heartbeat_interval', 300)
        )

        # Configuración de intervalos
        self.poll_interval = self.config.get('poll_interval_seconds', 300)
        self.sync_interval = self.config.get('sync_interval_seconds', 60)

        # Dispositivos
        self.devices_config = self.config.get('devices', [])
        self.zk_clients: dict[str, ZKClient] = {}

        # Cache de devices desde WebGUI DB (fuente única de verdad)
        self._devices_cache: list[dict] | None = None
        self._devices_cache_ts: float = 0
        self._devices_cache_ttl: int = 60

        # Estado
        self.last_poll: datetime | None = None
        self.last_sync: datetime | None = None
        self.last_heartbeat: datetime | None = None

        logger.info("AttendanceCollector inicializado")

    def _load_devices_from_webgui_db(self) -> list[dict]:
        """
        Cargar dispositivos desde la base de datos del WebGUI.

        Lee de WEBGUI_DB_PATH (default /app/data/webgui.db), tabla devices
        WHERE is_enabled=1 (esquema migrations/001). Cache TTL de 60s.
        Retorna lista vacía si la DB no existe o falla.
        """
        current_time = time.time()
        if (
            self._devices_cache is not None
            and (current_time - self._devices_cache_ts) < self._devices_cache_ttl
        ):
            logger.debug("Retornando dispositivos desde cache (TTL válido)")
            return self._devices_cache

        webgui_db_path = os.environ.get('WEBGUI_DB_PATH', '/app/data/webgui.db')

        if not Path(webgui_db_path).exists():
            logger.warning(f"WebGUI DB no encontrada en {webgui_db_path}, retornando lista vacía")
            self._devices_cache = []
            self._devices_cache_ts = current_time
            return []

        try:
            with sqlite3.connect(webgui_db_path, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, name, address as ip, port, password, timeout
                    FROM devices
                    WHERE is_enabled = 1
                ''')

                rows = cursor.fetchall()
                devices = [dict(row) for row in rows]

            self._devices_cache = devices
            self._devices_cache_ts = current_time
            logger.info(f"Cargados {len(devices)} dispositivos desde WebGUI DB")
            return devices

        except sqlite3.Error as e:
            logger.warning(f"Error leyendo WebGUI DB: {e}, retornando lista vacía")
            self._devices_cache = []
            self._devices_cache_ts = current_time
            return []
        except Exception as e:
            logger.warning(f"Error inesperado leyendo WebGUI DB: {e}, retornando lista vacía")
            self._devices_cache = []
            self._devices_cache_ts = current_time
            return []

    def _initialize_devices(self):
        """Inicializar clientes para cada dispositivo"""
        # WebGUI DB primero (fuente única de verdad); collector.yaml de fallback
        devices = self._load_devices_from_webgui_db()

        if devices:
            logger.info("Devices loaded from WebGUI DB")
        else:
            devices = self.devices_config
            logger.info("Devices loaded from collector.yaml (fallback)")

        for device in devices:
            # Solo collector.yaml usa 'enabled'; la WebGUI DB ya filtra is_enabled=1
            if 'enabled' in device and not device.get('enabled', True):
                logger.info(f"Dispositivo deshabilitado: {device.get('ip')}")
                continue

            ip = device.get('ip')
            if not ip:
                logger.warning(f"Dispositivo sin IP, omitiendo: {device.get('name')}")
                continue

            client = ZKClient(
                ip=ip,
                port=device.get('port', 4370),
                timeout=device.get('timeout', 5),
                password=device.get('password', 0)
            )
            self.zk_clients[ip] = client
            logger.info(f"Dispositivo configurado: {ip}")

    def poll_devices(self):
        """Polling de todos los dispositivos configurados"""
        # Refrescar lista de dispositivos desde la WebGUI DB si el TTL expiró
        current_devices = self._load_devices_from_webgui_db()

        if current_devices:
            current_ips = {d['ip'] for d in current_devices if d.get('ip')}
            existing_ips = set(self.zk_clients.keys())

            for ip in current_ips - existing_ips:
                device = next((d for d in current_devices if d['ip'] == ip), None)
                if device:
                    client = ZKClient(
                        ip=ip,
                        port=device.get('port', 4370),
                        timeout=device.get('timeout', 5),
                        password=device.get('password', 0)
                    )
                    self.zk_clients[ip] = client
                    logger.info(f"Nuevo dispositivo agregado: {ip}")

            for ip in existing_ips - current_ips:
                client = self.zk_clients.pop(ip, None)
                if client and client.connected:
                    client.disconnect()
                logger.info(f"Dispositivo removido: {ip}")

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
                    disable_device=True
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
            self.buffer.log_sync(0, 0, 'success', duration_seconds=0)
            return

        # Sincronizar
        success = self.platform_sync.sync_attendance(unsynced)

        duration = time.time() - start_time

        if success:
            # Marcar como sincronizados
            record_ids = [r['id'] for r in unsynced]
            self.buffer.mark_as_synced(record_ids)
            self.buffer.log_sync(
                records_synced=len(unsynced),
                records_failed=0,
                status='success',
                duration_seconds=duration
            )
            logger.info(f"Sincronización completada: {len(unsynced)} registros en {duration:.2f}s")
        else:
            # Marcar como fallido
            record_ids = [r['id'] for r in unsynced]
            self.buffer.mark_sync_failed(record_ids)
            self.buffer.log_sync(
                records_synced=0,
                records_failed=len(unsynced),
                status='failed',
                error_message='Platform error',
                duration_seconds=duration
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
