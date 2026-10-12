"""
Configuración de logging
"""

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Formatter para logs en formato JSON estructurado"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "device_ip"):
            log_entry["device_ip"] = record.device_ip
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
    max_size_mb: int = 10,
    backup_count: int = 5,
    log_format: str = "text",
) -> logging.Logger:
    """
    Configurar logging para la aplicación

    Args:
        log_dir: Directorio para archivos de log
        level: Nivel de logging
        max_size_mb: Tamaño máximo por archivo (MB)
        backup_count: Número de archivos de backup
        log_format: Formato de log ("text" o "json")

    Returns:
        Logger configurado
    """
    # Crear directorio de logs
    log_dir.mkdir(parents=True, exist_ok=True)

    # Logger principal
    logger = logging.getLogger("attendance_collector")
    logger.setLevel(level)
    logger.handlers.clear()

    # Formatter según formato
    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler de archivo (rotativo)
    log_file = log_dir / "collector.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_size_mb * 1024 * 1024, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler para errores (archivo separado)
    error_file = log_dir / "error.log"
    error_handler = RotatingFileHandler(
        error_file, maxBytes=max_size_mb * 1024 * 1024, backupCount=backup_count, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    logger.info(f"Logging configurado: {log_dir} (formato: {log_format})")

    return logger
