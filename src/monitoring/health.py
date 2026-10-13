"""
Health Monitor - Monitoreo de salud del colector
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any

import psutil

from src.sync.platform import PlatformSync

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitor de salud del colector

    Responsabilidades:
    - Enviar heartbeat periódico a plataforma
    - Recopilar métricas del sistema
    - Monitorear estado de dispositivos
    - Detectar condiciones anormales
    """

    def __init__(
        self,
        platform_sync: PlatformSync,
        interval: int = 300
    ):
        self.platform_sync = platform_sync
        self.interval = interval
        self.running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Estado de dispositivos
        self.devices_status: list[dict[str, Any]] = []

        # Métricas cached
        self.last_metrics: dict[str, Any] = {}

    def start(self):
        """Iniciar monitor en thread separado"""
        if self.running:
            return

        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"HealthMonitor iniciado (interval: {self.interval}s)")

    def stop(self):
        """Detener monitor"""
        if not self.running:
            return

        self.running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        logger.info("HealthMonitor detenido")

    def _run(self):
        """Loop principal del monitor"""
        while self.running and not self._stop_event.is_set():
            try:
                # Recopilar métricas
                metrics = self._collect_metrics()
                self.last_metrics = metrics

                # Enviar heartbeat
                success = self.platform_sync.send_heartbeat(
                    metrics=metrics,
                    devices_status=self.devices_status
                )

                if success:
                    logger.debug("Heartbeat enviado exitosamente")
                else:
                    logger.warning("Error enviando heartbeat")

            except Exception as e:
                logger.error(f"Error en HealthMonitor: {e}", exc_info=True)

            # Esperar intervalo
            self._stop_event.wait(self.interval)

    def _collect_metrics(self) -> dict[str, Any]:
        """
        Recopilar métricas del sistema

        Returns:
            Dict con métricas
        """
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # Memoria
            memory = psutil.virtual_memory()

            # Disco
            disk = psutil.disk_usage('/')

            # Temperatura (si está disponible)
            temperature = None
            try:
                sensors = psutil.sensors_temperatures()
                if 'cpu_thermal' in sensors:
                    temperature = sensors['cpu_thermal'][0].current
                elif 'bcm2835_thermal' in sensors:  # Raspberry Pi
                    temperature = sensors['bcm2835_thermal'][0].current
            except Exception:
                pass

            # Uptime
            uptime = time.time() - psutil.boot_time()

            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent,
                },
                'temperature': temperature,
                'uptime_seconds': uptime,
            }

            return metrics

        except Exception as e:
            logger.error(f"Error recopilando métricas: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def update_device_status(self, devices: list[dict[str, Any]]):
        """
        Actualizar estado de dispositivos

        Args:
            devices: Lista de estado de dispositivos
        """
        self.devices_status = devices

    def get_current_metrics(self) -> dict[str, Any]:
        """
        Obtener métricas actuales

        Returns:
            Dict con últimas métricas recopiladas
        """
        return self.last_metrics.copy()

    def get_system_health(self) -> dict[str, Any]:
        """
        Obtener resumen de salud del sistema

        Returns:
            Dict con estado de salud
        """
        metrics = self.last_metrics

        # Determinar estado general
        status = 'healthy'
        issues = []

        # Verificar CPU
        if metrics.get('cpu', {}).get('percent', 0) > 90:
            status = 'warning'
            issues.append('CPU usage high')

        # Verificar memoria
        if metrics.get('memory', {}).get('percent', 0) > 90:
            status = 'warning'
            issues.append('Memory usage high')

        # Verificar disco
        if metrics.get('disk', {}).get('percent', 0) > 90:
            status = 'critical'
            issues.append('Disk usage critical')

        # Verificar temperatura
        temp = metrics.get('temperature')
        if temp and temp > 80:
            status = 'critical'
            issues.append('Temperature critical')
        elif temp and temp > 70:
            status = 'warning'
            issues.append('Temperature high')

        return {
            'status': status,
            'issues': issues,
            'metrics': metrics,
            'devices_count': len(self.devices_status),
            'devices_online': sum(1 for d in self.devices_status if d.get('connected', False))
        }
