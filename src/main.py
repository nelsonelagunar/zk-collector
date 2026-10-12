#!/usr/bin/env python3
"""
Attendance Collector - ZKTeco Device Data Collector
Compilado con PyInstaller para Raspberry Pi 3

Author: nlaguna
Version: 1.0.0
License: MIT
"""

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

# Importar módulos del paquete
from src.core.collector import AttendanceCollector
from src.core.config import Config
from src.core.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
)
from src.utils.helpers import get_system_info
from src.utils.logging import setup_logging

# Metadatos
__version__ = "1.0.0"
__author__ = "nlaguna"


class Application:
    """Clase principal de la aplicación"""

    def __init__(self):
        self.config: Config | None = None
        self.collector: AttendanceCollector | None = None
        self.logger: logging.Logger | None = None
        self.running = False
        self.validate_only = False

        # Rutas críticas (configurables via env vars, con defaults en constants)
        self.config_path = Path(os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH))
        self.data_dir = Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR))
        self.log_dir = Path(os.environ.get("LOG_DIR", DEFAULT_LOG_DIR))

    def parse_args(self):
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(description="ZKTeco Attendance Collector")
        parser.add_argument(
            "--validate-config", action="store_true", help="Validate configuration and exit"
        )
        parser.add_argument("--config", type=str, help="Path to configuration file")
        parser.add_argument(
            "--log-format",
            choices=["text", "json"],
            default=os.environ.get("LOG_FORMAT", DEFAULT_LOG_FORMAT),
            help="Log format (text or json)",
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default=os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL),
            help="Log level",
        )
        args = parser.parse_args()

        self.validate_only = args.validate_config

        if args.config:
            self.config_path = Path(args.config)

        return args

    def initialize(self, log_format: str = "text", log_level: int = logging.INFO) -> bool:
        """Inicializar la aplicación"""
        try:
            # Crear directorios necesarios
            self._create_directories()

            # Configurar logging
            self.logger = setup_logging(
                log_dir=self.log_dir, level=log_level, log_format=log_format
            )
            self.logger.info("=" * 60)
            self.logger.info(f"Attendance Collector v{__version__}")
            self.logger.info("=" * 60)

            # Información del sistema
            sys_info = get_system_info()
            self.logger.info(f"Sistema: {sys_info['os']}")
            self.logger.info(f"Python: {sys_info['python']}")
            self.logger.info(f"RAM: {sys_info['ram']}")
            self.logger.info(f"CPU: {sys_info['cpu']}")

            # Validar configuración
            if not self.config_path.exists():
                self.logger.error(f"Archivo de configuración no encontrado: {self.config_path}")
                self.logger.error(
                    f"Copie configs/collector.yaml.example a {self.config_path} y edítelo"
                )
                return False

            # Cargar configuración
            self.config = Config(self.config_path)
            self.logger.info(f"Configuración cargada: {self.config_path}")

            # Validar configuración crítica
            if not self._validate_config():
                return False

            # Si solo validar, salir exitosamente
            if self.validate_only:
                self.logger.info("✓ Validación de configuración exitosa")
                return True

            # Inicializar colector
            self.collector = AttendanceCollector(self.config)
            self.logger.info("Colector inicializado correctamente")

            # Configurar señales
            self._setup_signals()

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error inicializando aplicación: {e}", exc_info=True)
            else:
                print(f"ERROR: {e}")
            return False

    def _create_directories(self):
        """Crear directorios necesarios"""
        for directory in [self.data_dir, self.log_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            # Permissions: rwxr-xr--
            os.chmod(directory, 0o754)

    def _validate_config(self) -> bool:
        """Validar configuración crítica"""
        required = ["platform.url", "platform.api_key", "platform.tenant_id", "devices"]

        for key in required:
            value = self.config.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                self.logger.error(f"Configuración requerida faltante: {key}")
                return False

        # Validar dispositivos
        devices = self.config.get("devices", [])
        if not devices:
            self.logger.error("No hay dispositivos configurados")
            return False

        for i, device in enumerate(devices):
            if "ip" not in device:
                self.logger.error(f"Dispositivo {i + 1} no tiene IP configurada")
                return False

        return True

    def _setup_signals(self):
        """Configurar manejo de señales"""

        def signal_handler(signum, frame):
            self.logger.info(f"Señal recibida: {signum}")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def run(self):
        """Ejecutar la aplicación"""
        if not self.initialize():
            sys.exit(1)

        # Si solo validar, salir
        if self.validate_only:
            sys.exit(0)

        self.running = True

        try:
            self.collector.run()
        except KeyboardInterrupt:
            self.logger.info("Interrupción por teclado")
        except Exception as e:
            self.logger.error(f"Error en ejecución: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.shutdown()

    def shutdown(self):
        """Apagado limpio de la aplicación"""
        if self.logger:
            self.logger.info("Iniciando apagado...")

        if self.collector:
            self.collector.stop()

        if self.logger:
            self.logger.info("Apagado completado")
            self.logger.info("=" * 60)


def main():
    """Entry point"""
    app = Application()
    args = app.parse_args()

    # Parse log level
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    log_level = log_level_map.get(args.log_level, logging.INFO)
    log_format = args.log_format

    if not app.initialize(log_format=log_format, log_level=log_level):
        sys.exit(1)

    if app.validate_only:
        sys.exit(0)

    app.run()


if __name__ == "__main__":
    main()
