"""
Configuración de logging
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    def format(self, record):
        import json
        log_obj = {
            'timestamp': self.formatTime(record, self.datefmt),
            'logger': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
    log_format: str = "text",
    max_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Configurar logging para la aplicación

    Args:
        log_dir: Directorio para archivos de log
        level: Nivel de logging
        log_format: Formato de log ("text" o "json")
        max_size_mb: Tamaño máximo por archivo (MB)
        backup_count: Número de archivos de backup

    Returns:
        Logger configurado
    """
    # Crear directorio de logs
    log_dir.mkdir(parents=True, exist_ok=True)

    # Logger principal
    logger = logging.getLogger('attendance_collector')
    logger.setLevel(level)
    logger.handlers.clear()

    # Formatter
    if log_format == "json":
        formatter: logging.Formatter = JsonFormatter(datefmt='%Y-%m-%d %H:%M:%S')
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler de archivo (rotativo)
    log_file = log_dir / 'collector.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler para errores (archivo separado)
    error_file = log_dir / 'error.log'
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    logger.info(f"Logging configurado: {log_dir}")

    return logger
