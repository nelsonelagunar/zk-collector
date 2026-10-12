"""
Funciones utilitarias
"""

import os
import platform
from typing import Any

import psutil


def get_system_info() -> dict[str, Any]:
    """
    Obtener información del sistema

    Returns:
        Dict con información del sistema
    """
    # Sistema operativo
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

    # Python
    python_version = f"{platform.python_version()} ({platform.python_implementation()})"

    # RAM
    memory = psutil.virtual_memory()
    ram_gb = memory.total / (1024**3)

    # CPU
    cpu_count = psutil.cpu_count()
    cpu_model = platform.processor() or "Unknown"

    return {
        "os": os_info,
        "python": python_version,
        "ram": f"{ram_gb:.2f} GB",
        "cpu": f"{cpu_count} cores ({cpu_model})",
        "hostname": platform.node(),
    }


def get_disk_usage(path: str = "/") -> dict[str, Any]:
    """
    Obtener uso de disco

    Args:
        path: Ruta a verificar

    Returns:
        Dict con uso de disco
    """
    disk = psutil.disk_usage(path)

    return {
        "total_gb": disk.total / (1024**3),
        "used_gb": disk.used / (1024**3),
        "free_gb": disk.free / (1024**3),
        "percent": disk.percent,
    }


def is_running_as_root() -> bool:
    """
    Verificar si se ejecuta como root

    Returns:
        bool: True si es root
    """
    return os.geteuid() == 0


def get_memory_usage() -> dict[str, Any]:
    """
    Obtener uso de memoria

    Returns:
        Dict con uso de memoria
    """
    memory = psutil.virtual_memory()
    process = psutil.Process(os.getpid())

    return {
        "system_percent": memory.percent,
        "process_mb": process.memory_info().rss / (1024**2),
    }


def format_bytes(bytes_value: int) -> str:
    """
    Formatear bytes a string legible

    Args:
        bytes_value: Valor en bytes

    Returns:
        String formateado (KB, MB, GB)
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_value) < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def truncate_string(s: str, max_length: int = 50) -> str:
    """
    Truncar string si excede longitud máxima

    Args:
        s: String a truncar
        max_length: Longitud máxima

    Returns:
        String truncado
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - 3] + "..."
